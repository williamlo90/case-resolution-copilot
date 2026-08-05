from pydantic import Field

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
from app.domain.actions import (
    ActionAttemptCommand,
    ActionAttemptOutcome,
    ActionCommand,
    ActionExecutionBlocker,
    ActionSideEffectState,
    ActionStatus,
    ManualActionOutcome,
    ReconciliationOutcome,
)
from app.domain.connections import ConnectionEnvironment, ConnectionHealth


class ActionSummaryResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    case_id: PublicId
    type: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=300)
    target: str = Field(min_length=1, max_length=200)
    impact: MoneyResponse | None
    status: ActionStatus
    execution_blocker: ActionExecutionBlocker | None
    attempt_count: int = Field(ge=0)
    owner: ActorSummaryResponse | None
    updated_at: UtcDateTime
    recovery_required: bool
    version: Version


class ActionAuthorityResponse(ApiSchema):
    actor: ActorSummaryResponse
    role: str = Field(min_length=1, max_length=100)
    rule: str = Field(min_length=1, max_length=300)


class ActionTargetConnectionResponse(ApiSchema):
    id: PublicId
    name: str = Field(min_length=1, max_length=200)
    environment: ConnectionEnvironment
    health: ConnectionHealth
    last_checked_at: UtcDateTime | None


class ActionAttemptResponse(ApiSchema):
    id: PublicId
    number: int = Field(ge=1)
    started_at: UtcDateTime
    finished_at: UtcDateTime | None
    actor: ActorSummaryResponse
    command: ActionAttemptCommand
    outcome: ActionAttemptOutcome
    side_effect_state: ActionSideEffectState
    detail: str = Field(min_length=1)


class ActionReceiptResponse(ApiSchema):
    id: PublicId
    provider: str = Field(min_length=1, max_length=100)
    external_reference: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=64)
    recorded_at: UtcDateTime


class ActionReconciliationResponse(ApiSchema):
    id: PublicId
    outcome: ReconciliationOutcome
    detail: str = Field(min_length=1, max_length=1000)
    external_reference: str | None = Field(default=None, max_length=200)
    checked_by: ActorSummaryResponse
    checked_at: UtcDateTime


class ApprovedProposalReferenceResponse(ApiSchema):
    id: PublicId
    version: Version
    review_id: PublicId
    approved_at: UtcDateTime
    snapshot_fingerprint: str = Field(min_length=1, max_length=128)


class ActionDetailResponse(ApiSchema):
    action: ActionSummaryResponse
    approved_proposal: ApprovedProposalReferenceResponse
    authority: ActionAuthorityResponse
    typed_parameters: dict[str, str]
    target_connection: ActionTargetConnectionResponse
    idempotency_key: str = Field(min_length=1, max_length=128)
    attempts: list[ActionAttemptResponse]
    receipt: ActionReceiptResponse | None
    reconciliations: list[ActionReconciliationResponse]
    expected_outcome: str = Field(min_length=1)
    observed_outcome: str | None
    execution_blocker: ActionExecutionBlocker | None
    available_commands: list[ActionCommand]


class ExecuteActionRequest(ApiSchema):
    expected_version: Version


class ReconcileActionRequest(ApiSchema):
    expected_version: Version


class RecordManualOutcomeRequest(ApiSchema):
    expected_version: Version
    outcome: ManualActionOutcome
    reason: str = Field(min_length=10, max_length=1000)


class EscalateActionRequest(ApiSchema):
    expected_version: Version
    reason: str = Field(min_length=10, max_length=1000)


class ActionDetailEnvelope(DataResponse[ActionDetailResponse]):
    pass


class ActionListResponse(CursorPage[ActionSummaryResponse]):
    pass
