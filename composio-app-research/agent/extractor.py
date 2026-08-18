import json
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from agent.models import (Evidence, SourceType, AuthMethod, CredentialAccess, APIType,
                          APIBreadth, MCPStatus, Buildability, AppResearch,
                          AuthExtraction, CredentialExtraction, APIExtraction, MCPExtraction)
from agent.evidence import extract_json_from_response, validate_and_repair_research


class NemotronExtractor:
    """5 claim-specific extraction methods."""

    def __init__(self, llm_client):
        self.llm = llm_client

    def _build_evidence_context(self, evidence: list, relevant_types: List[str] = None) -> str:
        """Build evidence context string for LLM."""
        filtered = evidence
        if relevant_types:
            filtered = [e for e in evidence if e.source_type.value in relevant_types]
        
        return "\n\n---\n\n".join([
            f"SOURCE: {e.url}\nTYPE: {e.source_type.value}\nCONTENT: {e.supporting_text[:2000]}"
            for e in filtered[:8]
        ])

    async def extract_auth(self, evidence: list) -> AuthExtraction:
        """Extract authentication methods."""
        evidence_text = self._build_evidence_context(evidence, 
            ['official_docs', 'auth_docs', 'web'])

        prompt = f"""You are an integration research analyst. Determine the authentication methods for this app using ONLY the evidence below.

EVIDENCE:
{evidence_text}

Return JSON:
{{
  "auth_methods": ["oauth2" | "api_key" | "basic" | "bearer_token" | "pat" | "service_account" | "other" | "multiple" | "unknown"],
  "confidence": 0.0-1.0,
  "citations": ["URL1", "URL2"]
}}

RULES:
1. Only use evidence provided. Mark "unknown" if evidence insufficient.
2. Look for explicit mentions of: OAuth 2.0, OAuth2, API key, API key authentication, Bearer token, Personal Access Token (PAT), Service Account, Basic Auth, Basic Authentication.
3. If multiple methods are clearly documented, use "multiple".
4. Return ONLY valid JSON. No markdown, no explanation."""

        return await self._extract_with_llm(prompt, 'auth')

    async def extract_credential(self, evidence: list) -> CredentialExtraction:
        """Extract credential accessibility."""
        evidence_text = self._build_evidence_context(evidence,
            ['official_docs', 'auth_docs', 'pricing_docs', 'web'])

        prompt = f"""You are an integration research analyst. Determine credential accessibility for this app using ONLY the evidence below.

EVIDENCE:
{evidence_text}

Return JSON:
{{
  "credential_access": "self_serve" | "self_serve_with_trial" | "paid_plan_required" | "admin_approval" | "partner_required" | "contact_sales" | "unknown",
  "confidence": 0.0-1.0,
  "citations": ["URL1", "URL2"]
}}

RULES:
1. Only use evidence provided. Mark "unknown" if evidence insufficient.
2. Self-serve = developer can get credentials immediately without sales/contact.
3. Self-serve with trial = free tier available but limited.
4. Paid plan required = must pay before getting credentials.
5. Admin approval = requires admin in customer's org.
5. Partner required = must be approved partner.
6. Contact sales = must talk to sales team.
7. Distinguish API existence from credential accessibility.
8. Return ONLY valid JSON. No markdown, no explanation."""

        return await self._extract_with_llm(prompt, 'credential')

    async def extract_api(self, evidence: list) -> APIExtraction:
        """Extract API types and breadth."""
        evidence_text = self._build_evidence_context(evidence,
            ['official_docs', 'api_docs', 'web'])

        prompt = f"""You are an integration research analyst. Determine API types and breadth for this app using ONLY the evidence below.

EVIDENCE:
{evidence_text}

Return JSON:
{{
  "api_types": ["rest" | "graphql" | "soap" | "grpc" | "webhooks" | "mcp" | "other"],
  "api_breadth": "broad" | "limited" | "unknown",
  "confidence": 0.0-1.0,
  "citations": ["URL1", "URL2"]
}}

RULES:
1. Only use evidence provided. Mark "unknown" if evidence insufficient.
2. Broad = comprehensive API covering most product features (CRUD operations, webhooks, batch operations, etc.).
2. Limited = narrow API (e.g., only webhooks, only specific resources, read-only).
3. Look for: REST, GraphQL, SOAP, gRPC, Webhooks, MCP, OpenAPI/Swagger, API reference docs.
3. Return ONLY valid JSON. No markdown, no explanation."""

        return await self._extract_with_llm(prompt, 'api')

    async def extract_mcp(self, evidence: list) -> MCPExtraction:
        """Extract MCP availability."""
        evidence_text = self._build_evidence_context(evidence,
            ['official_docs', 'mcp_registry', 'web'])

        prompt = f"""You are an integration research analyst. Determine if this app has a public MCP server using ONLY the evidence below.

EVIDENCE:
{evidence_text}

Return JSON:
{{
  "mcp_public": "yes" | "no" | "unknown",
  "confidence": 0.0-1.0,
  "citations": ["URL1", "URL2"]
}}

RULES:
1. Only use evidence provided. Mark "unknown" if evidence insufficient.
2. MCP = public Model Context Protocol server exists (not just Composio toolkit).
3. Look for: modelcontextprotocol.io, mcp. subdomain, "MCP server" in docs, "Model Context Protocol" in docs.
4. Return ONLY valid JSON. No markdown, no explanation."""

        return await self._extract_with_llm(prompt, 'mcp')

    def determine_buildability(self, auth: AuthExtraction, cred: CredentialExtraction, 
                               api: APIExtraction, mcp: MCPExtraction) -> tuple[str, str]:
        """Determine buildability with deterministic rules."""
        # Rules:
        # If credential access is explicitly blocked (contact_sales, partner_required) -> BLOCKED
        # If credential access requires admin approval -> HUMAN_OUTREACH_REQUIRED
        # If credential access is unknown -> UNKNOWN (not blocked)
        # If auth or API is unknown -> BUILDABLE_WITH_CAVEAT
        # Otherwise -> READY
        
        if cred.credential_access in [CredentialAccess.CONTACT_SALES, 
                                       CredentialAccess.PARTNER_REQUIRED]:
            return Buildability.BLOCKED.value, "Credential access requires sales/partner contact"
        
        if cred.credential_access == CredentialAccess.ADMIN_APPROVAL:
            return Buildability.HUMAN_OUTREACH_REQUIRED.value, "Requires admin approval"
        
        if cred.credential_access == CredentialAccess.UNKNOWN:
            return Buildability.UNKNOWN.value, "Credential access unknown"
        
        if auth.auth_methods == [AuthMethod.UNKNOWN] or api.api_types == [APIType.OTHER]:
            return Buildability.BUILDABLE_WITH_CAVEAT.value, "Auth or API type uncertain"
        
        return Buildability.READY.value, ""

    async def _extract_with_llm(self, prompt: str, field: str):
        """Call LLM and parse response."""
        response = await self.llm.complete_async(prompt, temperature=0.1, max_tokens=2000)
        
        data = extract_json_from_response(response)
        if data:
            # Validate required fields
            if field == 'auth':
                return AuthExtraction(
                    auth_methods=[AuthMethod(m) for m in data.get('auth_methods', ['unknown'])],
                    confidence=data.get('confidence', 0.0),
                    citations=data.get('citations', [])
                )
            elif field == 'credential':
                return CredentialExtraction(
                    credential_access=CredentialAccess(data.get('credential_access', 'unknown')),
                    confidence=data.get('confidence', 0.0),
                    citations=data.get('citations', [])
                )
            elif field == 'api':
                return APIExtraction(
                    api_types=[APIType(t) for t in data.get('api_types', ['other'])],
                    api_breadth=data.get('api_breadth', 'unknown'),
                    confidence=data.get('confidence', 0.0),
                    citations=data.get('citations', [])
                )
            elif field == 'mcp':
                return MCPExtraction(
                    mcp_public=MCPStatus(data.get('mcp_public', 'unknown')),
                    confidence=data.get('confidence', 0.0),
                    citations=data.get('citations', [])
                )
        
        # Fallback
        if field == 'auth':
            return AuthExtraction([AuthMethod.UNKNOWN], 0.0, [])
        elif field == 'credential':
            return CredentialExtraction(CredentialAccess.UNKNOWN, 0.0, [])
        elif field == 'api':
            return APIExtraction([APIType.OTHER], 'unknown', 0.0, [])
        elif field == 'mcp':
            return MCPExtraction(MCPStatus.UNKNOWN, 0.0, [])
        return None