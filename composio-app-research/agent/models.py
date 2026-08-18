from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field
from datetime import datetime


class AuthMethod(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC = "basic"
    BEARER_TOKEN = "bearer_token"
    PAT = "pat"
    SERVICE_ACCOUNT = "service_account"
    OTHER = "other"
    MULTIPLE = "multiple"
    UNKNOWN = "unknown"


class CredentialAccess(str, Enum):
    SELF_SERVE = "self_serve"
    SELF_SERVE_WITH_TRIAL = "self_serve_with_trial"
    PAID_PLAN_REQUIRED = "paid_plan_required"
    ADMIN_APPROVAL = "admin_approval"
    PARTNER_REQUIRED = "partner_required"
    CONTACT_SALES = "contact_sales"
    UNKNOWN = "unknown"


class APIType(str, Enum):
    REST = "rest"
    GRAPHQL = "graphql"
    SOAP = "soap"
    GRPC = "grpc"
    WEBHOOKS = "webhooks"
    MCP = "mcp"
    OTHER = "other"
    UNKNOWN = "unknown"


class APIBreadth(str, Enum):
    BROAD = "broad"
    LIMITED = "limited"
    UNKNOWN = "unknown"


class Buildability(str, Enum):
    READY = "ready"
    BUILDABLE_WITH_CAVEAT = "buildable_with_caveat"
    HUMAN_OUTREACH_REQUIRED = "human_outreach_required"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class MCPStatus(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    OFFICIAL_DOCS = "official_docs"
    AUTH_DOCS = "auth_docs"
    PRICING_DOCS = "pricing_docs"
    MARKETPLACE_DOCS = "marketplace_docs"
    WEB = "web"
    MCP_REGISTRY = "mcp_registry"
    COMPOSIO_REGISTRY = "composio_registry"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED_CORRECT = "verified_correct"
    VERIFIED_CORRECTED = "verified_corrected"


class ErrorType(str, Enum):
    AUTH_MISCLASSIFICATION = "AUTH_MISCLASSIFICATION"
    SELF_SERVE_CONFUSION = "SELF_SERVE_CONFUSION"
    PAID_PLAN_CONFUSION = "PAID_PLAN_CONFUSION"
    ENTERPRISE_GATE = "ENTERPRISE_GATE"
    PARTNER_GATE = "PARTNER_GATE"
    API_SCOPE_ERROR = "API_SCOPE_ERROR"
    MCP_FALSE_POSITIVE = "MCP_FALSE_POSITIVE"
    OUTDATED_DOC = "OUTDATED_DOC"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Evidence(BaseModel):
    claim: str
    url: str
    source_type: SourceType
    supporting_text: str
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class VerificationRecord(BaseModel):
    app: str
    field: str
    agent_answer: str
    verified_answer: str
    correct: bool
    error_type: ErrorType | None = None
    evidence: str


class AuthExtraction(BaseModel):
    auth_methods: list[AuthMethod]
    confidence: float
    citations: list[str]


class CredentialExtraction(BaseModel):
    credential_access: CredentialAccess
    confidence: float
    citations: list[str]


class APIExtraction(BaseModel):
    api_types: list[APIType]
    api_breadth: str  # broad, limited, unknown
    confidence: float
    citations: list[str]


class MCPExtraction(BaseModel):
    mcp_public: MCPStatus
    confidence: float
    citations: list[str]


class VerificationRecord(BaseModel):
    app: str
    field: str
    agent_answer: str
    verified_answer: str
    correct: bool
    error_type: ErrorType | None = None
    evidence: str


class AppResearch(BaseModel):
    app: str
    category: str
    description: str

    auth_methods: list[AuthMethod] = Field(default_factory=list)
    credential_access: CredentialAccess = CredentialAccess.UNKNOWN

    api_types: list[APIType] = Field(default_factory=list)
    api_breadth: APIBreadth = APIBreadth.UNKNOWN

    mcp_public: MCPStatus = MCPStatus.UNKNOWN
    composio_supported: MCPStatus = MCPStatus.UNKNOWN

    buildability: Buildability = Buildability.UNKNOWN
    blocker: str | None = None

    sources: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    uncertainty: list[str] = Field(default_factory=list)

    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verified_fields: dict[str, str] | None = None