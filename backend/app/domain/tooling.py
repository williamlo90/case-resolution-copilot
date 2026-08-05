from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.tools.contracts import SideEffectState


class ToolAttemptRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    tool_name: str
    outcome: str
    side_effect_state: SideEffectState
    idempotency_key: str | None
    request_data: dict[str, Any]
    response_data: dict[str, Any] | None
    error_code: str | None
    started_at: datetime
    finished_at: datetime


class ExternalReceiptRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tool_attempt_id: UUID
    provider: str
    tool_name: str
    external_reference: str
    idempotency_key: str
    status: str
    data: dict[str, Any]
    created_at: datetime
