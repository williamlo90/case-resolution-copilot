from typing import Literal

from pydantic import Field

from app.api.schemas.cases import (
    BusinessObjectSnapshotResponse,
    RiskCheckResponse,
    VerifiedFactResponse,
)
from app.api.schemas.common import (
    ActorSummaryResponse,
    ApiSchema,
    CursorPage,
    DataResponse,
    MoneyResponse,
    PublicId,
    UtcDateTime,
    Version,
)
from app.api.schemas.policies import PolicyEvidenceResponse
from app.api.schemas.proposals import (
    ProposalResponse,
    ProposalSummaryResponse,
    ProposedActionResponse,
)
from app.domain.reviews import ReviewDecision, ReviewStatus


class ReviewReservationResponse(ApiSchema):
    id: PublicId
    reviewer: ActorSummaryResponse
    reserved_at: UtcDateTime
    expires_at: UtcDateTime


class ReviewSnapshotFreshnessResponse(ApiSchema):
    status: Literal["current", "stale"]
    checked_at: UtcDateTime
    reason: str | None


class ReviewSummaryResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    case_id: PublicId
    proposal: ProposalSummaryResponse
    impact: MoneyResponse | None
    review_reason: str = Field(min_length=1)
    policy_state: Literal["supported", "possible_conflict", "missing"]
    uncertainty: Literal["low", "medium", "high"]
    submitted_by: ActorSummaryResponse
    submitted_at: UtcDateTime
    waiting_minutes: int = Field(ge=0)
    snapshot_freshness: ReviewSnapshotFreshnessResponse
    snapshot_fingerprint: str = Field(min_length=64, max_length=64)
    status: ReviewStatus
    reservation: ReviewReservationResponse | None
    version: Version


class ApprovalRuleResponse(ApiSchema):
    id: PublicId
    name: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1)
    required_role: str = Field(min_length=1, max_length=100)
    version: Version


class ReviewDecisionReceiptResponse(ApiSchema):
    id: PublicId
    review_id: PublicId
    decision: ReviewDecision
    reason: str = Field(min_length=1)
    actor: ActorSummaryResponse
    snapshot_fingerprint: str = Field(min_length=64, max_length=64)
    decided_at: UtcDateTime


class ReviewSnapshotResponse(ApiSchema):
    review: ReviewSummaryResponse
    case_version: Version
    context_fingerprint: str = Field(min_length=1, max_length=128)
    risk_rule_version: str = Field(min_length=1, max_length=100)
    facts: list[VerifiedFactResponse]
    business_contexts: list[BusinessObjectSnapshotResponse]
    evidence: list[PolicyEvidenceResponse]
    risks: list[RiskCheckResponse]
    proposal: ProposalResponse
    actions: list[ProposedActionResponse]
    approval_rule: ApprovalRuleResponse
    available_decisions: list[ReviewDecision]
    decision_history: list[ReviewDecisionReceiptResponse]


class ReserveReviewRequest(ApiSchema):
    expected_version: Version


class SubmitReviewRequest(ApiSchema):
    expected_case_version: Version


class DecideReviewRequest(ApiSchema):
    expected_version: Version
    snapshot_fingerprint: str = Field(min_length=64, max_length=64)
    decision: ReviewDecision
    reason: str = Field(min_length=1, max_length=2000)


class ReviewListResponse(CursorPage[ReviewSummaryResponse]):
    pass


class ReviewDetailEnvelope(DataResponse[ReviewSnapshotResponse]):
    pass
