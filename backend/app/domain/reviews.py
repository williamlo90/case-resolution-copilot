from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.cases import BusinessObjectRecord
from app.domain.decision_briefs import DecisionBriefRecord
from app.domain.identity import MemberRole
from app.domain.policies import PolicyEvidenceBundle


class ReviewStatus(StrEnum):
    PENDING = "pending"
    RESERVED = "reserved"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"
    ESCALATE = "escalate"


class ReviewPolicyState(StrEnum):
    SUPPORTED = "supported"
    POSSIBLE_CONFLICT = "possible_conflict"
    MISSING = "missing"


class ReviewUncertainty(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"


class ReviewReservationStatus(StrEnum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class ActorSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    role: MemberRole


class ApprovalRuleSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    explanation: str = Field(min_length=1, max_length=2000)
    required_role: MemberRole
    version: int = Field(ge=1)


class ReviewSubmission(BaseModel):
    expected_case_version: int = Field(ge=1)
    proposal_version: int = Field(ge=1)
    review_reason: str = Field(min_length=1, max_length=2000)
    policy_state: ReviewPolicyState
    uncertainty: ReviewUncertainty
    impact_amount: Decimal | None = Field(default=None, ge=0)
    impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    proposal_fingerprint: str = Field(min_length=64, max_length=64)
    context_fingerprint: str = Field(min_length=64, max_length=64)
    evidence_fingerprint: str = Field(min_length=64, max_length=64)
    risk_fingerprint: str = Field(min_length=64, max_length=64)
    risk_rule_version: str = Field(min_length=1, max_length=100)
    snapshot_fingerprint: str = Field(min_length=64, max_length=64)
    approval_rule: ApprovalRuleSnapshot
    execution_eligible: bool = True

    @model_validator(mode="after")
    def require_complete_impact(self) -> Self:
        if (self.impact_amount is None) != (self.impact_currency is None):
            raise ValueError("impact_amount and impact_currency must be supplied together")
        return self


class ReviewRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    proposal_id: UUID
    proposal_version_id: UUID
    status: ReviewStatus
    review_reason: str
    policy_state: ReviewPolicyState
    uncertainty: ReviewUncertainty
    impact_amount: Decimal | None
    impact_currency: str | None
    submitted_by_id: UUID
    submitted_by_public_id: str
    submitted_by_name: str
    submitted_by_role: MemberRole
    submitted_at: datetime
    version: int
    updated_at: datetime


class ReviewSnapshotRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    review_id: UUID
    proposal_id: UUID
    proposal_version_id: UUID
    case_version: int
    proposal_version: int
    proposal_fingerprint: str
    context_fingerprint: str
    evidence_fingerprint: str
    risk_fingerprint: str
    risk_rule_version: str
    snapshot_fingerprint: str
    approval_rule_id: str
    approval_rule_name: str
    approval_rule_explanation: str
    required_role: MemberRole
    approval_rule_version: int
    execution_eligible: bool
    created_at: datetime


class ReviewReservationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    review_id: UUID
    reviewer_id: UUID | None
    reviewer_public_id: str
    reviewer_name: str
    reviewer_role: MemberRole
    snapshot_fingerprint: str
    status: ReviewReservationStatus
    reserved_at: datetime
    expires_at: datetime
    consumed_at: datetime | None


class ReviewDecisionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    review_id: UUID
    reservation_id: UUID
    reviewer_id: UUID | None
    reviewer_public_id: str
    reviewer_name: str
    reviewer_role: MemberRole
    decision: ReviewDecision
    reason: str
    snapshot_fingerprint: str
    decided_at: datetime


class ReviewBundleRecord(BaseModel):
    review: ReviewRecord
    snapshot: ReviewSnapshotRecord
    case_public_id: str
    proposal_public_id: str
    reservation: ReviewReservationRecord | None
    decisions: list[ReviewDecisionRecord]


class ReviewFreshnessRecord(BaseModel):
    status: ReviewFreshness
    checked_at: datetime
    reason: str | None


class ReviewQueueItemRecord(BaseModel):
    bundle: ReviewBundleRecord
    proposal_public_id: str
    proposal_outcome: str
    freshness: ReviewFreshnessRecord


class ReviewPageRecord(BaseModel):
    items: list[ReviewQueueItemRecord]
    next_cursor: str | None
    total: int


class ReviewDetailRecord(BaseModel):
    bundle: ReviewBundleRecord
    brief: DecisionBriefRecord
    business_contexts: list[BusinessObjectRecord]
    evidence: list[PolicyEvidenceBundle]
    freshness: ReviewFreshnessRecord
    available_decisions: list[ReviewDecision]


class LegacyReviewImport(BaseModel):
    legacy_reservation_id: UUID
    legacy_decision_id: UUID | None
    legacy_proposal_version_id: UUID
    reviewer_public_id: str
    reviewer_name: str
    reviewer_role: MemberRole
    source_proposal_version: int = Field(ge=1)
    source_evidence_fingerprint: str = Field(min_length=1, max_length=128)
    decision: ReviewDecision | None
    reason: str = Field(min_length=1, max_length=2000)
    reserved_at: datetime
    expires_at: datetime
    decided_at: datetime | None

    @model_validator(mode="after")
    def require_complete_legacy_decision(self) -> Self:
        if self.expires_at <= self.reserved_at:
            raise ValueError("legacy reservation expiry must follow its start")
        has_decision = self.decision is not None
        if has_decision != (self.legacy_decision_id is not None):
            raise ValueError("legacy decision and lineage ID must be supplied together")
        if has_decision != (self.decided_at is not None):
            raise ValueError("legacy decision and timestamp must be supplied together")
        return self


class ReviewNotFound(LookupError):
    pass


class ReviewConflict(RuntimeError):
    pass


class ReviewSubmissionNotAllowed(RuntimeError):
    pass


class ReviewDecisionNotAllowed(RuntimeError):
    pass


class ReviewAuthorityDenied(PermissionError):
    pass


class ReviewSnapshotStale(RuntimeError):
    pass


class ReviewReservationExpired(RuntimeError):
    pass


class ReviewVersionConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The review changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


class InvalidReviewCursor(ValueError):
    pass
