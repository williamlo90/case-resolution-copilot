from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class ExternalConversationModel(Base):
    __tablename__ = "external_conversations"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_external_conversations_version"),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_external_conversations_org_id",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_external_conversations_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            "provider_thread_id",
            name="uq_external_conversations_org_provider_thread",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            name="uq_external_conversations_org_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_external_conversations_org_connection",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_external_conversations_org_case",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "thread_id"],
            ["conversation_threads.organization_id", "conversation_threads.id"],
            name="fk_external_conversations_org_thread",
            ondelete="CASCADE",
        ),
        Index(
            "ix_external_conversations_org_latest",
            "organization_id",
            "latest_message_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider_thread_id: Mapped[str] = mapped_column(String(500), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    first_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latest_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latest_provider_message_id: Mapped[str] = mapped_column(String(500), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ExternalMessageModel(Base):
    __tablename__ = "external_messages"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="ck_external_messages_direction",
        ),
        CheckConstraint("attachment_count >= 0", name="ck_external_messages_attachments"),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_external_messages_org_id",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_external_messages_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            "provider_message_id",
            name="uq_external_messages_org_provider_message",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_external_messages_org_connection",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "external_conversation_id"],
            ["external_conversations.organization_id", "external_conversations.id"],
            name="fk_external_messages_org_conversation",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "conversation_message_id"],
            ["conversation_messages.organization_id", "conversation_messages.id"],
            name="fk_external_messages_org_local_message",
            ondelete="CASCADE",
        ),
        Index(
            "ix_external_messages_org_conversation_received",
            "organization_id",
            "external_conversation_id",
            "provider_received_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    external_conversation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    conversation_message_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String(500), nullable=False)
    rfc_message_id: Mapped[str | None] = mapped_column(String(1000))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    sender: Mapped[dict[str, str | None]] = mapped_column(JSONB, nullable=False)
    recipients: Mapped[list[dict[str, str | None]]] = mapped_column(JSONB, nullable=False)
    provider_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sanitized_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    omission_reason: Mapped[str | None] = mapped_column(String(500))
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ExternalAttachmentModel(Base):
    __tablename__ = "external_attachments"
    __table_args__ = (
        CheckConstraint("reported_size >= 0", name="ck_external_attachments_size"),
        CheckConstraint(
            "content_status IN ('metadata_only', 'available', 'unsupported', "
            "'too_large', 'blocked', 'deleted')",
            name="ck_external_attachments_content_status",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_external_attachments_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "external_message_id",
            "provider_attachment_id",
            name="uq_external_attachments_org_provider",
        ),
        ForeignKeyConstraint(
            ["organization_id", "external_message_id"],
            ["external_messages.organization_id", "external_messages.id"],
            name="fk_external_attachments_org_message",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    external_message_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider_attachment_id: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    reported_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_status: Mapped[str] = mapped_column(String(32), nullable=False)
    local_evidence_reference: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    parser_status: Mapped[str] = mapped_column(String(32), nullable=False)
    malware_scan_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
