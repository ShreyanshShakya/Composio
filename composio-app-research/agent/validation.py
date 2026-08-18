from dataclasses import dataclass

from agent.models import (
    APIExtraction,
    AuthExtraction,
    CredentialExtraction,
    Evidence,
    MCPExtraction,
)


@dataclass
class ValidationResult:
    valid: bool
    warnings: list[str]


def validate_extraction_citations(extraction, evidence: list[Evidence], field: str) -> ValidationResult:
    """Validate that LLM citations point to evidence actually supplied to the extraction."""
    evidence_urls = {item.url for item in evidence}
    citations = [str(url).strip() for url in getattr(extraction, "citations", []) if str(url).strip()]
    warnings: list[str] = []

    invalid = [url for url in citations if url not in evidence_urls]
    if invalid:
        warnings.append(f"{field}: {len(invalid)} citation(s) were not present in supplied evidence")

    value_is_unknown = False
    if isinstance(extraction, AuthExtraction):
        value_is_unknown = all(getattr(item, "value", str(item)) == "unknown" for item in extraction.auth_methods)
    elif isinstance(extraction, CredentialExtraction):
        value_is_unknown = getattr(extraction.credential_access, "value", str(extraction.credential_access)) == "unknown"
    elif isinstance(extraction, APIExtraction):
        value_is_unknown = all(getattr(item, "value", str(item)) in {"unknown", "other"} for item in extraction.api_types)
    elif isinstance(extraction, MCPExtraction):
        value_is_unknown = getattr(extraction.mcp_public, "value", str(extraction.mcp_public)) == "unknown"

    if value_is_unknown and citations:
        warnings.append(f"{field}: extraction is unknown/other despite having citations; retain uncertainty")

    return ValidationResult(valid=not invalid, warnings=warnings)
