import asyncio
import json
import random
from typing import List
from agent.models import (Evidence, SourceType, AuthMethod, CredentialAccess, APIType,
                          APIBreadth, MCPStatus, Buildability, AppResearch,
                          AuthExtraction, CredentialExtraction, APIExtraction, MCPExtraction)
from agent.evidence import extract_json_from_response


class NemotronExtractor:
    """Claim-specific extraction methods using the configured LLM client."""

    _llm_semaphore = asyncio.Semaphore(1)
    _last_llm_request = 0.0
    _llm_min_interval = 1.0

    def __init__(self, llm_client, max_retries: int = 4):
        self.llm = llm_client
        self.max_retries = max_retries

    def _build_evidence_context(self, evidence: list, relevant_types: List[str] = None) -> str:
        filtered = evidence
        if relevant_types:
            filtered = [e for e in evidence if e.source_type.value in relevant_types]
        return "\n\n---\n\n".join(
            f"SOURCE: {e.url}\nTYPE: {e.source_type.value}\nCONTENT: {e.supporting_text[:2000]}"
            for e in filtered[:8]
        )

    async def extract_auth(self, evidence: list) -> AuthExtraction:
        evidence_text = self._build_evidence_context(evidence, ['official_docs', 'auth_docs', 'web'])
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
        evidence_text = self._build_evidence_context(evidence, ['official_docs', 'auth_docs', 'pricing_docs', 'web'])
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
6. Partner required = must be approved partner.
7. Contact sales = must talk to sales team.
8. Distinguish API existence from credential accessibility.
9. Return ONLY valid JSON. No markdown, no explanation."""
        return await self._extract_with_llm(prompt, 'credential')

    async def extract_api(self, evidence: list) -> APIExtraction:
        evidence_text = self._build_evidence_context(evidence, ['official_docs', 'api_docs', 'web'])
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
3. Limited = narrow API (e.g., only webhooks, only specific resources, read-only).
4. Look for: REST, GraphQL, SOAP, gRPC, Webhooks, MCP, OpenAPI/Swagger, API reference docs.
5. Return ONLY valid JSON. No markdown, no explanation."""
        return await self._extract_with_llm(prompt, 'api')

    async def extract_mcp(self, evidence: list) -> MCPExtraction:
        evidence_text = self._build_evidence_context(evidence, ['official_docs', 'mcp_registry', 'web'])
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
        if cred.credential_access in [CredentialAccess.CONTACT_SALES, CredentialAccess.PARTNER_REQUIRED]:
            return Buildability.BLOCKED.value, "Credential access requires sales/partner contact"
        if cred.credential_access == CredentialAccess.ADMIN_APPROVAL:
            return Buildability.HUMAN_OUTREACH_REQUIRED.value, "Requires admin approval"
        if cred.credential_access == CredentialAccess.UNKNOWN:
            return Buildability.UNKNOWN.value, "Credential access unknown"
        if auth.auth_methods == [AuthMethod.UNKNOWN] or api.api_types == [APIType.OTHER]:
            return Buildability.BUILDABLE_WITH_CAVEAT.value, "Auth or API type uncertain"
        return Buildability.READY.value, ""

    async def _extract_with_llm(self, prompt: str, field: str):
        """Call the configured LLM with serialized access and 429-aware backoff."""
        provider = type(self.llm).__name__
        for attempt in range(self.max_retries + 1):
            try:
                async with self._llm_semaphore:
                    loop = asyncio.get_running_loop()
                    now = loop.time()
                    wait = self._llm_min_interval - (now - self._last_llm_request)
                    if wait > 0:
                        await asyncio.sleep(wait)
                    self._last_llm_request = loop.time()
                    response = await self.llm.complete_async(prompt, temperature=0.1, max_tokens=2000)

                data = extract_json_from_response(response)
                if data:
                    if field == 'auth':
                        return AuthExtraction(auth_methods=[AuthMethod(m) for m in data.get('auth_methods', ['unknown'])], confidence=data.get('confidence', 0.0), citations=data.get('citations', []))
                    if field == 'credential':
                        return CredentialExtraction(credential_access=CredentialAccess(data.get('credential_access', 'unknown')), confidence=data.get('confidence', 0.0), citations=data.get('citations', []))
                    if field == 'api':
                        return APIExtraction(api_types=[APIType(t) for t in data.get('api_types', ['other'])], api_breadth=data.get('api_breadth', 'unknown'), confidence=data.get('confidence', 0.0), citations=data.get('citations', []))
                    if field == 'mcp':
                        return MCPExtraction(mcp_public=MCPStatus(data.get('mcp_public', 'unknown')), confidence=data.get('confidence', 0.0), citations=data.get('citations', []))
                return self._fallback(field)
            except Exception as exc:
                error = str(exc).lower()
                retryable = any(token in error for token in ('429', 'rate limit', 'too many requests', 'timeout', '500', '502', '503', '504'))
                if not retryable or attempt >= self.max_retries:
                    print(f"[{provider}] {field} failed: {exc}")
                    break
                base = 5.0 if any(token in error for token in ('429', 'rate limit', 'too many requests')) else 2.0
                delay = min(base * (2 ** attempt) + random.uniform(0, 2), 60.0)
                print(f"[{provider}] {field} attempt {attempt + 1} rate-limited; retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
        return self._fallback(field)

    @staticmethod
    def _fallback(field: str):
        if field == 'auth':
            return AuthExtraction(auth_methods=[AuthMethod.UNKNOWN], confidence=0.0, citations=[])
        if field == 'credential':
            return CredentialExtraction(credential_access=CredentialAccess.UNKNOWN, confidence=0.0, citations=[])
        if field == 'api':
            return APIExtraction(api_types=[APIType.OTHER], api_breadth='unknown', confidence=0.0, citations=[])
        if field == 'mcp':
            return MCPExtraction(mcp_public=MCPStatus.UNKNOWN, confidence=0.0, citations=[])
        return None
