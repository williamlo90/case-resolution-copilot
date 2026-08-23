from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.cases import CaseCategory, CaseRisk, CaseUrgency

from .messages import AttachmentContentStatus, MessageDirection


class ExternalConversationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    connection_id: UUID
    case_id: UUID
    thread_id: UUID
    provider_thread_id: str
    subject: str
    first_message_at: datetime
    latest_message_at: datetime
    latest_provider_message_id: str
    source_fingerprint: str
    version: int
    created_at: datetime
    updated_at: datetime


class ExternalMessageRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    connection_id: UUID
    external_conversation_id: UUID
    conversation_message_id: UUID
    provider_message_id: str
    rfc_message_id: str | None
    direction: MessageDirection
    sender: dict[str, str | None]
    recipients: list[dict[str, str | None]]
    provider_received_at: datetime
    observed_at: datetime
    sanitized_content_hash: str
    raw_source_hash: str
    parser_version: str
    omission_reason: str | None
    attachment_count: int
    source_metadata: dict[str, str | int | bool | None]
    created_at: datetime


class ExternalAttachmentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    external_message_id: UUID
    provider_attachment_id: str
    name: str
    media_type: str
    reported_size: int
    content_status: AttachmentContentStatus
    local_evidence_reference: str | None
    content_hash: str | None
    parser_status: str
    malware_scan_status: str
    created_at: datetime


class SelectedThreadImportCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_thread_id: str
    category: CaseCategory
    urgency: CaseUrgency
    risk: CaseRisk
    due_at: datetime


class ImportedCaseHandle(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: UUID
    case_public_id: str
    thread_id: UUID
    first_local_message_id: UUID


class InboxImportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_public_id: str
    external_conversation_public_id: str
    imported_messages: int
    duplicate_messages: int
    conversation_fingerprint: str
    latest_message_at: datetime
