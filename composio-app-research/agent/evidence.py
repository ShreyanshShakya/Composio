import json
import re
from typing import Any
from datetime import datetime
from agent.models import Evidence, SourceType, AppResearch, AuthMethod, CredentialAccess, APIType, APIBreadth, MCPStatus, Buildability


def extract_json_from_response(response: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown code blocks."""
    response = response.strip()
    
    if response.startswith("```json"):
        response = response[7:]
    if response.startswith("```"):
        response = response[3:]
    if response.endswith("```"):
        response = response[:-3]
    
    response = response.strip()
    
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def validate_and_repair_research(data: dict, app_name: str, max_retries: int = 2) -> AppResearch | None:
    """Validate research output against schema, with repair retry logic."""
    from pydantic import ValidationError
    from agent.models import AppResearch, APIBreadth, MCPStatus, Buildability
    
    # Normalize data: convert single-element arrays to values for string fields
    string_fields = ['credential_access', 'api_breadth', 'mcp_public', 'composio_supported', 'buildability', 'blocker', 'description']
    for field in string_fields:
        if field in data and isinstance(data[field], list) and len(data[field]) > 0:
            data[field] = data[field][0]
    
    # Normalize array fields - handle string 'unknown' 
    array_fields = ['auth_methods', 'api_types', 'uncertainty']
    for field in array_fields:
        if field in data:
            if isinstance(data[field], str):
                data[field] = [data[field]] if data[field] else []
            elif not isinstance(data[field], list):
                data[field] = []
    
    for attempt in range(max_retries + 1):
        try:
            return AppResearch(**data)
        except ValidationError as e:
            if attempt >= max_retries:
                print(f"[{app_name}] Validation failed after {max_retries} retries: {e}")
                return None
            
            error_msg = str(e)
            print(f"[{app_name}] Validation error (attempt {attempt + 1}): {error_msg}")
            
            repair_prompt = f"""
The previous response failed validation. Fix these errors:

{error_msg}

Return ONLY the corrected JSON matching the AppResearch schema.
"""
            data = None  # Signal to caller to retry with repair prompt
    
    return None


def normalize_source_type(url: str, context: str = "") -> SourceType:
    """Classify source type from URL and context."""
    url_lower = url.lower()
    context_lower = context.lower()
    
    if any(x in url_lower for x in ["developer.", "docs.", "api.", "developer-docs."]):
        if "auth" in url_lower or "auth" in context_lower or "oauth" in context_lower:
            return SourceType.AUTH_DOCS
        if "pricing" in url_lower or "plan" in url_lower or "billing" in context_lower:
            return SourceType.PRICING_DOCS
        if "marketplace" in url_lower or "integration" in url_lower or "app." in url_lower:
            return SourceType.MARKETPLACE_DOCS
        return SourceType.OFFICIAL_DOCS
    
    if "mcp" in url_lower or "modelcontextprotocol" in url_lower:
        return SourceType.MCP_REGISTRY
    
    if "composio" in url_lower:
        return SourceType.COMPOSIO_REGISTRY
    
    return SourceType.WEB


def calculate_confidence(research: AppResearch) -> float:
    """Calculate confidence score based on evidence quality and completeness."""
    score = 0.0
    factors = 0
    
    # Evidence count factor
    evidence_count = len(research.evidence)
    if evidence_count >= 5:
        score += 0.25
    elif evidence_count >= 3:
        score += 0.15
    elif evidence_count >= 1:
        score += 0.05
    factors += 0.25
    
    # Source diversity factor
    source_types = set(e.source_type for e in research.evidence)
    if SourceType.OFFICIAL_DOCS in source_types or SourceType.AUTH_DOCS in source_types:
        score += 0.25
    factors += 0.25
    
    # Field completeness factor
    fields = [
        research.auth_methods != [AuthMethod.UNKNOWN],
        research.credential_access != CredentialAccess.UNKNOWN,
        research.api_types != [APIType.OTHER],
        research.api_breadth != APIBreadth.UNKNOWN,
        research.mcp_public != MCPStatus.UNKNOWN,
        research.buildability != Buildability.UNKNOWN,
    ]
    filled = sum(1 for f in fields if f)
    score += (filled / len(fields)) * 0.35
    factors += 0.35
    
    # Uncertainty penalty
    uncertainty_penalty = min(len(research.uncertainty) * 0.05, 0.15)
    score -= uncertainty_penalty
    
    return max(0.0, min(1.0, score))