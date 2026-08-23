from typing import Literal

from pydantic import Field

from app.api.schemas.common import (
    ApiSchema,
    CursorPage,
    DataResponse,
    MoneyResponse,
    PublicId,
    SourceFreshnessResponse,
    UtcDateTime,
    Version,
)
from app.api.schemas.conversations import ConversationThreadResponse
from app.api.schemas.policies import PolicyEvidenceResponse
from app.api.schemas.proposals import (
    ProposalResponse,
    ProposedActionResponse,
    ResponseDraftResponse,
)
from app.domain.cases import (
    BusinessObjectType,
    CaseCategory,
    CaseCommand,
    CaseRisk,
    CaseStatus,
    CaseUrgency,
)


class CaseOwnerResponse(ApiSchema):
    id: PublicId
    name: str = Field(min_length=1, max_length=200)
    initials: str = Field(min_length=1, max_length=3)


class CaseCustomerSummaryResponse(ApiSchema):
    name: str = Field(min_length=1, max_length=200)
    is_vip: bool


class CaseSummaryResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    source_id: str = Field(min_length=1, max_length=200)
    external_reference: str = Field(min_length=1, max_length=200)
    category: CaseCategory
    issue: str = Field(min_length=1, max_length=500)
    customer: CaseCustomerSummaryResponse
    status: CaseStatus
    owner: CaseOwnerResponse | None
    urgency: CaseUrgency
    risk: CaseRisk
    sla_minutes_remaining: int = Field(ge=0)
    updated_at: UtcDateTime | None
    source_freshness: SourceFreshnessResponse
    impact: MoneyResponse | None
    version: Version


class CaseRequestResponse(ApiSchema):
    id: PublicId
    received_at: UtcDateTime
    channel: Literal["email", "chat", "phone", "webhook"]
    customer_message: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class CustomerContextResponse(ApiSchema):
    id: PublicId
    tier: Literal["standard", "vip", "enterprise"]
    locale: str = Field(min_length=1, max_length=35)
    contact: str = Field(min_length=1, max_length=320)


class BusinessObjectSnapshotResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    case_id: PublicId
    type: Literal["invoice", "payment", "subscription", "account", "order", "delivery", "other"]
    label: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=100)
    source_reference: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=100)
    fields: dict[str, str]
    captured_at: UtcDateTime
    source_freshness: SourceFreshnessResponse
    version: Version


class VerifiedFactResponse(ApiSchema):
    id: PublicId
    statement: str = Field(min_length=1)
    source: str = Field(min_length=1, max_length=300)
    verified_at: UtcDateTime


class MissingInformationResponse(ApiSchema):
    id: PublicId
    label: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1)
    blocking: bool


class RiskCheckResponse(ApiSchema):
    id: PublicId
    label: str = Field(min_length=1, max_length=300)
    outcome: Literal["passed", "requires_review", "information_needed", "blocked"]
    explanation: str = Field(min_length=1)


class CaseActivityResponse(ApiSchema):
    id: PublicId
    label: str = Field(min_length=1, max_length=300)
    detail: str = Field(min_length=1)
    actor: str = Field(min_length=1, max_length=200)
    timestamp: UtcDateTime
    status: Literal["completed", "current", "waiting", "failed"]


class CaseCollectionWindowResponse(ApiSchema):
    returned: int = Field(ge=0)
    total: int = Field(ge=0)
    has_more: bool
    next_cursor: str | None


class CaseWorkspaceCollectionsResponse(ApiSchema):
    business_contexts: CaseCollectionWindowResponse
    messages: CaseCollectionWindowResponse
    activity: CaseCollectionWindowResponse


class CaseWorkspaceResponse(ApiSchema):
    case: CaseSummaryResponse
    request: CaseRequestResponse
    conversation: ConversationThreadResponse
    customer: CustomerContextResponse
    business_contexts: list[BusinessObjectSnapshotResponse]
    facts: list[VerifiedFactResponse]
    missing_information: list[MissingInformationResponse]
    evidence: list[PolicyEvidenceResponse]
    risks: list[RiskCheckResponse]
    proposal: ProposalResponse | None
    response_draft: ResponseDraftResponse | None
    proposed_actions: list[ProposedActionResponse]
    activity: list[CaseActivityResponse]
    collections: CaseWorkspaceCollectionsResponse
    available_commands: list[CaseCommand]


class CaseQueueSummaryResponse(ApiSchema):
    total: int = Field(ge=0)
    attention: int = Field(ge=0)
    review: int = Field(ge=0)
    sla_at_risk: int = Field(ge=0)
    unassigned: int = Field(ge=0)


class CaseListResponse(CursorPage[CaseSummaryResponse]):
    previous_cursor: str | None
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    summary_scope: Literal["organization"]
    summary: CaseQueueSummaryResponse


class CaseDetailResponse(DataResponse[CaseWorkspaceResponse]):
    pass


class CaseActivityPageResponse(CursorPage[CaseActivityResponse]):
    pass


class CaseIntakeReceiptResponse(ApiSchema):
    id: PublicId
    source_id: str = Field(min_length=1, max_length=200)
    duplicate: bool


class CaseIntakeResponse(DataResponse[CaseIntakeReceiptResponse]):
    pass


class AssignCaseRequest(ApiSchema):
    expected_version: Version


class ChangeCaseStatusRequest(ApiSchema):
    expected_version: Version
    status: CaseStatus


class AddCaseEvidenceRequest(ApiSchema):
    expected_case_version: Version
    type: BusinessObjectType
    label: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=100)
    source_reference: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=100)
    fields: dict[str, str] = Field(default_factory=dict, max_length=12)
