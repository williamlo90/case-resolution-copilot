from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskType(StrEnum):
    REFUND = "refund"


class RequestChannel(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"


class TaskCreate(BaseModel):
    public_id: str = Field(pattern=r"^RF-\d{4}$")
    task_type: TaskType = TaskType.REFUND
    customer_message: str = Field(min_length=1)
    channel: RequestChannel
    received_at: datetime
    correlation_id: str = Field(min_length=1, max_length=128)
    summary: str = "Refund request"
    due_at: datetime | None = None
    exposure_amount: Decimal | None = Field(default=None, ge=0)
    exposure_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @field_validator("received_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("received_at must be timezone-aware UTC")
        return value

    def effective_due_at(self) -> datetime:
        return self.due_at or datetime.now(UTC) + timedelta(minutes=60)


class TaskRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    task_type: TaskType
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    summary: str
    due_at: datetime
    exposure_amount: Decimal | None
    exposure_currency: str | None


class RequestRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    channel: RequestChannel
    customer_message: str
    received_at: datetime
    correlation_id: str
