from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.connections import ConnectionRecord
from app.domain.identity import MemberRole


class ActionStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_SAFE = "failed_safe"
    OUTCOME_UNKNOWN = "outcome_unknown"
    RECOVERY_REQUIRED = "recovery_required"


class ActionAttemptOutcome(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED_BEFORE_CHANGE = "failed_before_change"
    UNKNOWN = "unknown"


class ActionSideEffectState(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    NONE = "none"
    CONFIRMED = "confirmed"
    POSSIBLE = "possible"


class ActionExecutionBlocker(StrEnum):
    PERMISSION = "permission"
    DUPLICATE = "duplicate"
    EXPIRED_APPROVAL = "expired_approval"
    CONNECTION_UNAVAILABLE = "connection_unavailable"
    STALE_PROPOSAL = "stale_proposal"


class ActionCommand(StrEnum):
    EXECUTE = "execute"
    RETRY_SAFE = "retry_safe"
    RECONCILE = "reconcile"
    RECORD_MANUAL_OUTCOME = "record_manual_outcome"
    ESCALATE = "escalate"


class ActionAttemptCommand(StrEnum):
    EXECUTE = "execute"
    RETRY_SAFE = "retry_safe"
    LEGACY_IMPORT = "legacy_import"


class ReconciliationOutcome(StrEnum):
    RUNNING = "running"
    CONFIRMED_COMPLETED = "confirmed_completed"
    CONFIRMED_ABSENT = "confirmed_absent"
    STILL_UNKNOWN = "still_unknown"


class ManualActionOutcome(StrEnum):
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"


class LegacyActionReceiptImport(BaseModel):
    legacy_external_receipt_id: UUID
    provider: str = Field(min_length=1, max_length=100)
    external_reference: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=64)
    data_fingerprint: str = Field(min_length=64, max_length=64)
    recorded_at: datetime


class LegacyActionImport(BaseModel):
    legacy_tool_attempt_id: UUID
    legacy_proposal_version_id: UUID
    source_tool_name: str = Field(min_length=1, max_length=100)
    action_type: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=200)
    parameters: dict[str, str]
    status: ActionStatus
    attempt_outcome: ActionAttemptOutcome
    side_effect_state: ActionSideEffectState
    idempotency_key: str = Field(min_length=16, max_length=128)
    observed_outcome: str = Field(min_length=1, max_length=1000)
    error_code: str | None = Field(default=None, max_length=100)
    request_fingerprint: str = Field(min_length=64, max_length=64)
    response_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    started_at: datetime
    finished_at: datetime
    receipt: LegacyActionReceiptImport | None = None

    @model_validator(mode="after")
    def require_consistent_historical_outcome(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("legacy action finish must not precede its start")
        if self.status is ActionStatus.COMPLETED:
            if (
                self.receipt is None
                or self.attempt_outcome is not ActionAttemptOutcome.SUCCEEDED
                or self.side_effect_state is not ActionSideEffectState.CONFIRMED
            ):
                raise ValueError("completed legacy actions require a confirmed attempt and receipt")
        elif self.status is ActionStatus.FAILED_SAFE:
            if (
                self.attempt_outcome is not ActionAttemptOutcome.FAILED_BEFORE_CHANGE
                or self.side_effect_state
                not in {
                    ActionSideEffectState.NOT_ATTEMPTED,
                    ActionSideEffectState.NONE,
                }
            ):
                raise ValueError("safe legacy failures require proof that no change occurred")
        elif self.status is not ActionStatus.OUTCOME_UNKNOWN:
            raise ValueError(
                "legacy action imports must be completed, failed safe, or outcome unknown"
            )
        return self


class ActionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    proposal_id: UUID
    proposal_version_id: UUID
    proposed_action_id: UUID
    review_id: UUID
    review_snapshot_id: UUID
    review_decision_id: UUID
    connection_id: UUID
    legacy_proposal_version_id: UUID | None
    type: str
    label: str
    target: str
    typed_parameters: dict[str, str]
    impact_amount: Decimal | None
    impact_currency: str | None
    expected_outcome: str
    observed_outcome: str | None
    status: ActionStatus
    execution_blocker: ActionExecutionBlocker | None
    execution_eligible: bool
    idempotency_key: str
    authorization_expires_at: datetime
    owner_id: UUID | None
    owner_public_id: str | None
    owner_name: str | None
    attempt_count: int
    version: int
    created_at: datetime
    updated_at: datetime


class ActionAttemptRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    action_id: UUID
    actor_id: UUID | None
    actor_public_id: str
    actor_name: str
    actor_role: MemberRole | None
    legacy_tool_attempt_id: UUID | None
    number: int
    command: ActionAttemptCommand
    outcome: ActionAttemptOutcome
    side_effect_state: ActionSideEffectState
    detail: str
    error_code: str | None
    request_fingerprint: str
    response_fingerprint: str | None
    started_at: datetime
    finished_at: datetime | None


class ActionReceiptRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    action_id: UUID
    attempt_id: UUID
    legacy_external_receipt_id: UUID | None
    provider: str
    external_reference: str
    idempotency_key: str
    status: str
    data_fingerprint: str
    recorded_at: datetime


class ActionReconciliationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    action_id: UUID
    actor_id: UUID
    actor_public_id: str
    actor_name: str
    outcome: ReconciliationOutcome
    detail: str
    external_reference: str | None
    checked_at: datetime


class ActionBundleRecord(BaseModel):
    action: ActionRecord
    case_public_id: str
    proposal_public_id: str
    proposal_version: int
    review_public_id: str
    review_snapshot_fingerprint: str
    approved_at: datetime
    approved_by_public_id: str
    approved_by_name: str
    approved_by_role: MemberRole
    approval_rule: str
    connection: ConnectionRecord
    attempts: list[ActionAttemptRecord]
    receipt: ActionReceiptRecord | None
    reconciliations: list[ActionReconciliationRecord]


class ActionQueueItemRecord(BaseModel):
    bundle: ActionBundleRecord
    effective_blocker: ActionExecutionBlocker | None
    recovery_required: bool


class ActionPageRecord(BaseModel):
    items: list[ActionQueueItemRecord]
    next_cursor: str | None
    total: int


class ActionExecutionLease(BaseModel):
    action_id: UUID
    action_public_id: str
    action_version: int
    attempt_id: UUID
    attempt_public_id: str
    organization_public_id: str
    action_type: str
    target: str
    parameters: dict[str, str]
    idempotency_key: str
    adapter_key: str
    provider_type: str


class ActionReconciliationLease(BaseModel):
    action_id: UUID
    action_public_id: str
    action_version: int
    reconciliation_id: UUID
    organization_public_id: str
    action_type: str
    target: str
    parameters: dict[str, str]
    idempotency_key: str
    external_reference: str | None
    adapter_key: str
    provider_type: str


class ActionNotFound(LookupError):
    pass


class ActionConflict(RuntimeError):
    pass


class InvalidActionCursor(ValueError):
    pass


class ActionExecutionBlocked(RuntimeError):
    def __init__(self, blocker: ActionExecutionBlocker, message: str) -> None:
        super().__init__(message)
        self.blocker = blocker


class ActionVersionConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The action changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version
