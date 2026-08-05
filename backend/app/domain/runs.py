from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED_VERIFIED = "completed_verified"
    FAILED_NO_SIDE_EFFECT = "failed_no_side_effect"
    EXECUTION_UNCERTAIN = "execution_uncertain"
    RECONCILING = "reconciling"
    ESCALATED = "escalated"


TERMINAL_RUN_STATES = frozenset({RunStatus.COMPLETED_VERIFIED, RunStatus.ESCALATED})

_ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.ESCALATED}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING_APPROVAL,
            RunStatus.COMPLETED_VERIFIED,
            RunStatus.FAILED_NO_SIDE_EFFECT,
            RunStatus.EXECUTION_UNCERTAIN,
            RunStatus.ESCALATED,
        }
    ),
    RunStatus.WAITING_APPROVAL: frozenset({RunStatus.QUEUED, RunStatus.ESCALATED}),
    RunStatus.COMPLETED_VERIFIED: frozenset(),
    RunStatus.FAILED_NO_SIDE_EFFECT: frozenset({RunStatus.QUEUED, RunStatus.ESCALATED}),
    RunStatus.EXECUTION_UNCERTAIN: frozenset({RunStatus.RECONCILING, RunStatus.ESCALATED}),
    RunStatus.RECONCILING: frozenset(
        {
            RunStatus.COMPLETED_VERIFIED,
            RunStatus.FAILED_NO_SIDE_EFFECT,
            RunStatus.EXECUTION_UNCERTAIN,
            RunStatus.ESCALATED,
        }
    ),
    RunStatus.ESCALATED: frozenset(),
}


class InvalidRunTransition(ValueError):
    pass


def validate_run_transition(current: RunStatus, target: RunStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidRunTransition(f"Run cannot transition from {current} to {target}.")


class AgentRunCreate(BaseModel):
    public_id: str = Field(pattern=r"^AR-[A-Z0-9]{4,12}$")
    task_id: UUID
    correlation_id: str = Field(min_length=1, max_length=128)


class AgentRunRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    task_id: UUID
    status: RunStatus
    version: int
    correlation_id: str
    model_provider: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    graph_version: str | None = None
    created_at: datetime
    updated_at: datetime
