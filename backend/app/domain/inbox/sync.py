from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InboxImportMode(StrEnum):
    PAUSED = "paused"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class InboxSyncStatus(StrEnum):
    CURRENT = "current"
    SYNCING = "syncing"
    DELAYED = "delayed"
    FAILED = "failed"
    REAUTHORIZE = "reauthorize"


class SyncJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


class SyncTrigger(StrEnum):
    CONNECT = "connect"
    MANUAL = "manual"
    SCHEDULE = "schedule"
    PUSH = "push"
    RECOVERY = "recovery"


class InboxConnectionProfileRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    connection_id: UUID
    provider_account_id: str
    account_address: str
    import_mode: InboxImportMode
    label_filter: list[str]
    initial_window_days: int
    initial_item_limit: int
    watch_expires_at: datetime | None
    last_successful_sync_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class InboxSyncCheckpointRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    connection_id: UUID
    provider_history_id: str | None
    last_observed_history_id: str | None
    status: InboxSyncStatus
    consecutive_failures: int
    last_error_code: str | None
    last_attempt_at: datetime | None
    last_successful_sync_at: datetime | None
    last_recovery_at: datetime | None
    version: int


class InboxSyncJobRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    connection_id: UUID
    trigger: SyncTrigger
    trigger_key: str
    requested_history_id: str | None
    page_token: str | None
    status: SyncJobStatus
    page_budget: int
    item_budget: int
    attempt_count: int
    available_at: datetime
    lease_owner: str | None
    lease_expires_at: datetime | None
    last_error_code: str | None
    completed_at: datetime | None
    created_at: datetime


class InboxSyncWorkRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    job: InboxSyncJobRecord
    organization_public_id: str
    connection_public_id: str
    committed_history_id: str | None


class SyncRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    connection_public_id: str = Field(min_length=1, max_length=64)
    trigger: SyncTrigger
    trigger_key: str = Field(min_length=1, max_length=200)
    requested_history_id: str | None = Field(default=None, max_length=500)
    page_token: str | None = Field(default=None, max_length=2000)
    page_budget: int = Field(default=5, ge=1, le=10)
    item_budget: int = Field(default=50, ge=1, le=100)


class InboxSyncDrainResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    claimed_jobs: int
    completed_jobs: int
    failed_jobs: int
    imported_messages: int
    duplicate_messages: int
