from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class AttachmentContentStatus(StrEnum):
    METADATA_ONLY = "metadata_only"
    AVAILABLE = "available"
    UNSUPPORTED = "unsupported"
    TOO_LARGE = "too_large"
    BLOCKED = "blocked"
    DELETED = "deleted"


class MessageAddress(BaseModel):
    model_config = ConfigDict(frozen=True)

    address: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=200)


class ProviderAttachment(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_attachment_id: str = Field(min_length=1, max_length=500)
    name: str = Field(min_length=1, max_length=500)
    media_type: str = Field(min_length=1, max_length=200)
    reported_size: int = Field(ge=0, le=100_000_000)
    content_status: AttachmentContentStatus = AttachmentContentStatus.METADATA_ONLY


class ProviderMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_message_id: str = Field(min_length=1, max_length=500)
    provider_thread_id: str = Field(min_length=1, max_length=500)
    rfc_message_id: str | None = Field(default=None, max_length=1000)
    subject: str = Field(min_length=1, max_length=500)
    sender: MessageAddress
    recipients: tuple[MessageAddress, ...] = Field(max_length=50)
    direction: MessageDirection
    received_at: datetime
    body: str = Field(min_length=1, max_length=100_000)
    sanitized_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    raw_source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parser_version: str = Field(min_length=1, max_length=64)
    omission_reason: str | None = Field(default=None, max_length=500)
    attachments: tuple[ProviderAttachment, ...] = Field(default=(), max_length=25)


class ProviderThread(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_thread_id: str = Field(min_length=1, max_length=500)
    history_id: str | None = Field(default=None, max_length=500)
    messages: tuple[ProviderMessage, ...] = Field(min_length=1, max_length=100)


class ProviderThreadSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_thread_id: str = Field(min_length=1, max_length=500)
    subject: str = Field(min_length=1, max_length=500)
    latest_message_at: datetime


class ThreadPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[ProviderThreadSummary, ...] = Field(max_length=100)
    next_page_token: str | None = Field(default=None, max_length=2000)
    history_id: str | None = Field(default=None, max_length=500)


class ChangePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_message_ids: tuple[str, ...] = Field(max_length=100)
    next_page_token: str | None = Field(default=None, max_length=2000)
    history_id: str = Field(min_length=1, max_length=500)
