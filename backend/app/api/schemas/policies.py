from typing import Literal, Self

from pydantic import Field, model_validator

from app.api.schemas.common import (
    ActorSummaryResponse,
    ApiSchema,
    CursorPage,
    DataResponse,
    PublicId,
    UtcDateTime,
    Version,
)
from app.domain.cases import CaseCategory
from app.domain.policies import (
    EvidenceRetrievalStatus,
    PolicyVersionStatus,
)
from app.domain.policies import (
    PolicyLifecycleStatus as PolicyStatus,
)


class PolicySourceResponse(ApiSchema):
    kind: Literal["upload", "url", "manual"]
    name: str = Field(min_length=1, max_length=500)


class PolicySummaryResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=1000)
    status: PolicyStatus
    owner: ActorSummaryResponse
    applies_to: list[str] = Field(min_length=1)
    current_version: int = Field(ge=0)
    effective_from: UtcDateTime | None
    effective_to: UtcDateTime | None
    source: PolicySourceResponse
    health: Literal["healthy", "review_due", "conflict", "expired", "source_error"]
    used_by_cases: int = Field(ge=0)
    version: Version
    updated_at: UtcDateTime


class PolicyClauseResponse(ApiSchema):
    id: PublicId
    heading: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1)
    applies_when: str = Field(min_length=1)


class PolicyCaseReferenceResponse(ApiSchema):
    case_id: PublicId
    citation: str = Field(min_length=1)
    recorded_at: UtcDateTime


class PolicyApplicabilityResponse(ApiSchema):
    decision_scope: str = Field(min_length=1, max_length=100)
    case_categories: list[str] = Field(min_length=1)
    products: list[str] = Field(min_length=1)
    regions: list[str] = Field(min_length=1)
    channels: list[str] = Field(min_length=1)
    customer_tiers: list[str] = Field(min_length=1)


class PolicyVersionResponse(ApiSchema):
    id: PublicId
    policy_id: PublicId
    version: Version
    record_version: Version
    status: PolicyVersionStatus
    immutable: bool
    created_at: UtcDateTime
    published_at: UtcDateTime | None
    effective_from: UtcDateTime | None
    effective_to: UtcDateTime | None
    applicability: PolicyApplicabilityResponse
    source_text: str = Field(min_length=1)
    clauses: list[PolicyClauseResponse] = Field(min_length=1)
    used_by_cases: list[PolicyCaseReferenceResponse]


class PolicyEvidenceResponse(ApiSchema):
    id: PublicId
    policy_id: PublicId
    policy_version_id: PublicId
    policy_version: Version
    clause_id: PublicId
    title: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    applicability: str = Field(min_length=1)
    effective_date: str = Field(min_length=1)
    freshness: Literal["current", "stale"]
    conflict_state: Literal["none", "possible", "confirmed"]
    fingerprint: str = Field(min_length=1, max_length=128)


class PolicyDetailResponse(ApiSchema):
    policy: PolicySummaryResponse
    versions: list[PolicyVersionResponse]
    available_commands: list[
        Literal[
            "create_draft",
            "submit_review",
            "publish",
            "schedule",
            "retire",
            "retry_source",
        ]
    ]


class PolicyListResponse(CursorPage[PolicySummaryResponse]):
    pass


class PolicyDetailEnvelope(DataResponse[PolicyDetailResponse]):
    pass


class PolicyApplicabilityRequest(ApiSchema):
    decision_scope: str = Field(min_length=1, max_length=100)
    case_categories: list[CaseCategory | Literal["all"]] = Field(min_length=1)
    products: list[str] = Field(min_length=1)
    regions: list[str] = Field(min_length=1)
    channels: list[Literal["email", "chat", "phone", "webhook", "all"]] = Field(min_length=1)
    customer_tiers: list[Literal["standard", "vip", "enterprise", "all"]] = Field(min_length=1)


class EffectiveWindowRequest(ApiSchema):
    effective_from: UtcDateTime | None = None
    effective_to: UtcDateTime | None = None

    @model_validator(mode="after")
    def require_effective_order(self) -> Self:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to must be after effective_from")
        return self


class CreatePolicyRequest(EffectiveWindowRequest):
    public_id: str | None = Field(default=None, pattern=r"^POL-[A-Z0-9-]+$", max_length=64)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=1000)
    source: PolicySourceResponse
    source_text: str | None = Field(default=None, max_length=200_000)
    applicability: PolicyApplicabilityRequest | None = None


class CreatePolicyDraftRequest(EffectiveWindowRequest):
    expected_policy_version: Version
    source_text: str = Field(min_length=20, max_length=200_000)
    applicability: PolicyApplicabilityRequest


class PolicyVersionCommandRequest(ApiSchema):
    expected_policy_version: Version
    expected_version: Version


class PublishPolicyVersionRequest(PolicyVersionCommandRequest):
    effective_from: UtcDateTime | None = None


class SchedulePolicyVersionRequest(PolicyVersionCommandRequest):
    effective_from: UtcDateTime


class RetryPolicySourceRequest(EffectiveWindowRequest):
    expected_policy_version: Version
    source_text: str = Field(min_length=20, max_length=200_000)
    applicability: PolicyApplicabilityRequest


class PolicyEvidenceResultResponse(ApiSchema):
    status: EvidenceRetrievalStatus
    reason: str = Field(min_length=1)
    evidence: list[PolicyEvidenceResponse]


class PolicyEvidenceEnvelope(DataResponse[PolicyEvidenceResultResponse]):
    pass
