from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DraftDeliveryStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_SAFE = "failed_safe"
    OUTCOME_UNKNOWN = "outcome_unknown"
    RECOVERY_REQUIRED = "recovery_required"


class DraftLookupStatus(StrEnum):
    FOUND = "found"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"
    UNAVAILABLE = "unavailable"


class CreateDraftRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_thread_id: str = Field(min_length=1, max_length=500)
    recipient: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10_000)
    in_reply_to: str | None = Field(default=None, max_length=1000)
    references: tuple[str, ...] = Field(default=(), max_length=50)
    correlation_key: str = Field(pattern=r"^[a-f0-9]{64}$")


class DraftReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_draft_id: str = Field(min_length=1, max_length=500)
    provider_message_id: str = Field(min_length=1, max_length=500)
    provider_thread_id: str = Field(min_length=1, max_length=500)
    created_at: datetime


class FindDraftRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_thread_id: str = Field(min_length=1, max_length=500)
    correlation_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    recipient: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=300)
    body_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    not_before: datetime


class DraftLookupResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: DraftLookupStatus
    receipt: DraftReceipt | None = None
    absence_is_terminal: bool = False

    @model_validator(mode="after")
    def require_consistent_receipt(self) -> "DraftLookupResult":
        if (self.status is DraftLookupStatus.FOUND) != (self.receipt is not None):
            raise ValueError("Only a found draft lookup may include a receipt.")
        if self.absence_is_terminal and self.status is not DraftLookupStatus.ABSENT:
            raise ValueError("Terminal absence evidence requires an absent result.")
        return self


class DraftDeliveryRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    external_conversation_id: UUID
    connection_id: UUID
    response_draft_id: UUID
    response_draft_version: int
    review_id: UUID | None
    decision_fingerprint: str
    evidence_fingerprint: str
    policy_fingerprint: str
    conversation_fingerprint: str
    response_fingerprint: str
    provider_thread_id: str
    recipient: str
    subject_snapshot: str
    body_hash: str
    in_reply_to: str | None
    references: list[str]
    idempotency_key: str
    status: DraftDeliveryStatus
    provider_draft_id: str | None
    provider_message_id: str | None
    attempt_count: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    last_error_code: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CaseDraftContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: UUID
    case_id: UUID
    case_public_id: str
    case_version: int
    response_draft_id: UUID
    response_draft_version: int
    subject: str
    body: str
    response_fingerprint: str


class ReviewDraftAuthorization(BaseModel):
    model_config = ConfigDict(frozen=True)

    review_id: UUID
    snapshot_fingerprint: str
    evidence_fingerprint: str
    policy_fingerprint: str


class InboxReplyContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    external_conversation_id: UUID
    connection_id: UUID
    connection_public_id: str
    provider_thread_id: str
    recipient: str
    in_reply_to: str | None
    references: tuple[str, ...]
    conversation_fingerprint: str


class DraftDeliveryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    delivery: DraftDeliveryRecord
    provider_draft_url: str | None = None
