from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReviewerRole(StrEnum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    AUDITOR = "auditor"
    ADMINISTRATOR = "administrator"


class ReservationStatus(StrEnum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class ApprovalOutcome(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFORMATION = "needs_information"


class ReviewerReservationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proposal_id: UUID
    reviewer_id: str
    reviewer_role: ReviewerRole
    proposal_version: int
    evidence_fingerprint: str
    status: ReservationStatus
    expires_at: datetime
    created_at: datetime
    consumed_at: datetime | None


class ApprovalDecisionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proposal_id: UUID
    reservation_id: UUID
    outcome: ApprovalOutcome
    reason: str
    reviewer_id: str
    reviewer_role: ReviewerRole
    proposal_version: int
    evidence_fingerprint: str
    decided_at: datetime
