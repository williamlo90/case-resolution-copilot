from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationKind(StrEnum):
    SLA_RISK = "sla_risk"
    REVIEW_WAITING = "review_waiting"
    ACTION_RECOVERY = "action_recovery"
    MEMBERSHIP_CHANGED = "membership_changed"
    SETTINGS_CHANGED = "settings_changed"
    SYSTEM = "system"


class NotificationStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"


class NotificationResourceType(StrEnum):
    CASE = "case"
    REVIEW = "review"
    ACTION = "action"
    CONNECTION = "connection"
    MEMBER = "member"
    SETTINGS = "settings"
    SYSTEM = "system"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    SKIPPED = "skipped"
    FAILED = "failed"


class NotificationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: UUID
    public_id: str
    organization_id: UUID
    recipient_id: UUID
    recipient_public_id: str
    kind: NotificationKind
    status: NotificationStatus
    title: str
    message: str
    resource_type: NotificationResourceType
    resource_public_id: str
    event_key: str
    version: int = Field(ge=1)
    created_at: datetime
    read_at: datetime | None


class NotificationPageRecord(BaseModel):
    items: list[NotificationRecord]
    next_cursor: str | None
    total: int
    unread_count: int


class NotificationSeed(BaseModel):
    recipient_public_id: str = Field(min_length=1, max_length=64)
    kind: NotificationKind
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)
    resource_type: NotificationResourceType
    resource_public_id: str = Field(min_length=1, max_length=64)
    event_key: str = Field(min_length=1, max_length=200)


class NotificationNotFound(LookupError):
    pass


class InvalidNotificationCursor(ValueError):
    pass


class NotificationConflict(RuntimeError):
    pass


class NotificationVersionConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The notification changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version
