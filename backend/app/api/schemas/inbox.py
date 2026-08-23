from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.cases import CaseCategory, CaseRisk, CaseUrgency
from app.domain.connections import ConnectionHealth, CredentialStatus
from app.domain.inbox import (
    DraftDeliveryStatus,
    InboxImportMode,
    InboxSyncStatus,
    SyncJobStatus,
)


class InboxAuthorizationCommand(BaseModel):
    include_drafts: bool = False
    return_path: str = Field(default="/connections", min_length=1, max_length=500)
    login_hint: EmailStr | None = None


class InboxAuthorizationStartData(BaseModel):
    authorization_url: str
    expires_at: datetime


class InboxAuthorizationStartEnvelope(BaseModel):
    data: InboxAuthorizationStartData


class InboxCallbackCommand(BaseModel):
    state: str = Field(min_length=32, max_length=512)
    code: str = Field(min_length=1, max_length=4000)


class InboxConnectionData(BaseModel):
    connection_id: str
    account_address: str
    return_path: str
    capabilities: list[str]


class InboxConnectionEnvelope(BaseModel):
    data: InboxConnectionData


class InboxConnectionStatusData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    connection_public_id: str
    account_address: str
    import_mode: InboxImportMode
    health: ConnectionHealth
    credential_status: CredentialStatus
    sync_status: InboxSyncStatus
    capabilities: tuple[str, ...]
    last_checked_at: datetime | None
    last_successful_sync_at: datetime | None
    last_error_code: str | None


class InboxConnectionStatusEnvelope(BaseModel):
    data: InboxConnectionStatusData


class InboxThreadData(BaseModel):
    provider_thread_id: str
    subject: str
    latest_message_at: datetime


class InboxThreadListResponse(BaseModel):
    items: list[InboxThreadData]
    next_cursor: str | None


class InboxImportCommand(BaseModel):
    provider_thread_id: str = Field(min_length=1, max_length=500)
    category: CaseCategory
    urgency: CaseUrgency
    risk: CaseRisk
    due_at: datetime


class InboxImportData(BaseModel):
    case_id: str
    conversation_id: str
    imported_messages: int
    duplicate_messages: int
    latest_message_at: datetime


class InboxImportEnvelope(BaseModel):
    data: InboxImportData


class InboxSyncJobData(BaseModel):
    id: str
    status: SyncJobStatus
    attempt_count: int


class InboxSyncJobEnvelope(BaseModel):
    data: InboxSyncJobData


class InboxCommandData(BaseModel):
    status: str
    provider_revoked: bool | None = None


class InboxCommandEnvelope(BaseModel):
    data: InboxCommandData


class ScheduledSyncCommand(BaseModel):
    organization_id: str = Field(pattern=r"^ORG-[A-Z0-9-]+$", max_length=64)
    connection_id: str = Field(min_length=1, max_length=64)
    trigger_key: str = Field(min_length=1, max_length=200)


class SyncDrainData(BaseModel):
    claimed_jobs: int
    completed_jobs: int
    failed_jobs: int
    imported_messages: int
    duplicate_messages: int


class SyncDrainEnvelope(BaseModel):
    data: SyncDrainData


class DraftDeliveryCommand(BaseModel):
    expected_draft_version: int = Field(ge=1)


class DraftDeliveryData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: DraftDeliveryStatus
    attempt_count: int
    provider_draft_id: str | None
    last_error_code: str | None


class DraftDeliveryEnvelope(BaseModel):
    data: DraftDeliveryData


class DraftDeliveryLookupEnvelope(BaseModel):
    data: DraftDeliveryData | None
