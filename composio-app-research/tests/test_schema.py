import pytest
from agent.models import (
    AppResearch, Evidence, AuthMethod, CredentialAccess, APIType,
    APIBreadth, Buildability, MCPStatus, SourceType, VerificationStatus
)
from datetime import datetime


def test_auth_method_enum():
    assert AuthMethod.OAUTH2.value == "oauth2"
    assert AuthMethod.API_KEY.value == "api_key"
    assert AuthMethod.UNKNOWN.value == "unknown"
    assert len(AuthMethod) == 9


def test_credential_access_enum():
    assert CredentialAccess.SELF_SERVE.value == "self_serve"
    assert CredentialAccess.CONTACT_SALES.value == "contact_sales"
    assert CredentialAccess.UNKNOWN.value == "unknown"
    assert len(CredentialAccess) == 7


def test_api_type_enum():
    assert APIType.REST.value == "rest"
    assert APIType.GRAPHQL.value == "graphql"
    assert APIType.MCP.value == "mcp"
    assert APIType.UNKNOWN.value == "unknown"
    assert len(APIType) == 8


def test_buildability_enum():
    assert Buildability.READY.value == "ready"
    assert Buildability.BLOCKED.value == "blocked"
    assert Buildability.UNKNOWN.value == "unknown"
    assert len(Buildability) == 5


def test_mcp_status_enum():
    assert MCPStatus.YES.value == "yes"
    assert MCPStatus.NO.value == "no"
    assert MCPStatus.UNKNOWN.value == "unknown"
    assert len(MCPStatus) == 3


def test_evidence_model():
    ev = Evidence(
        claim="Uses OAuth2",
        url="https://slack.com/auth",
        source_type=SourceType.AUTH_DOCS,
        supporting_text="Slack uses OAuth 2.0 for authentication...",
    )
    assert ev.claim == "Uses OAuth2"
    assert ev.source_type == SourceType.AUTH_DOCS
    assert isinstance(ev.retrieved_at, datetime)


def test_app_research_minimal():
    research = AppResearch(
        app="TestApp",
        category="Test Category",
        description="A test app",
    )
    assert research.app == "TestApp"
    assert research.auth_methods == []
    assert research.credential_access == CredentialAccess.UNKNOWN
    assert research.confidence == 0.0


def test_app_research_full():
    research = AppResearch(
        app="Slack",
        category="Communications and Messaging",
        description="Team communication platform",
        auth_methods=[AuthMethod.OAUTH2, AuthMethod.API_KEY],
        credential_access=CredentialAccess.SELF_SERVE,
        api_types=[APIType.REST, APIType.WEBHOOKS],
        api_breadth=APIBreadth.BROAD,
        mcp_public=MCPStatus.NO,
        composio_supported=MCPStatus.YES,
        buildability=Buildability.READY,
        blocker=None,
        evidence=[
            Evidence(
                claim="OAuth2 documented",
                url="https://api.slack.com/authentication/oauth-v2",
                source_type=SourceType.AUTH_DOCS,
                supporting_text="Slack uses OAuth 2.0...",
            )
        ],
        confidence=0.95,
        uncertainty=["API breadth could be verified further"],
        verification_status=VerificationStatus.VERIFIED_CORRECT,
    )
    assert research.app == "Slack"
    assert len(research.auth_methods) == 2
    assert research.credential_access == CredentialAccess.SELF_SERVE
    assert research.confidence == 0.95


def test_confidence_bounds():
    with pytest.raises(ValueError):
        AppResearch(app="Test", category="Test", description="Test", confidence=1.5)
    
    with pytest.raises(ValueError):
        AppResearch(app="Test", category="Test", description="Test", confidence=-0.1)


def test_serialization():
    research = AppResearch(
        app="TestApp",
        category="Test",
        description="Test",
        auth_methods=[AuthMethod.OAUTH2],
        credential_access=CredentialAccess.SELF_SERVE,
    )
    
    json_str = research.model_dump_json()
    assert "TestApp" in json_str
    assert "oauth2" in json_str
    assert "self_serve" in json_str
    
    # Round-trip
    restored = AppResearch.model_validate_json(json_str)
    assert restored.app == "TestApp"
    assert restored.auth_methods == [AuthMethod.OAUTH2]


def test_evidence_source_types():
    for st in SourceType:
        ev = Evidence(
            claim="Test",
            url="https://example.com",
            source_type=st,
            supporting_text="Test content",
        )
        assert ev.source_type == st


if __name__ == "__main__":
    pytest.main([__file__, "-v"])