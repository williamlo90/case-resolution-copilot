from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class CaseModel(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_cases_version_positive"),
        CheckConstraint(
            "category IN ('billing_dispute', 'refund_request', 'account_access', "
            "'service_exception')",
            name="ck_cases_category",
        ),
        CheckConstraint(
            "status IN ('new', 'investigating', 'information_needed', 'needs_review', "
            "'waiting_customer', 'in_progress', 'completed')",
            name="ck_cases_status",
        ),
        CheckConstraint(
            "urgency IN ('low', 'medium', 'high', 'critical')", name="ck_cases_urgency"
        ),
        CheckConstraint("risk IN ('low', 'medium', 'high')", name="ck_cases_risk"),
        CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_cases_impact_pair",
        ),
        CheckConstraint(
            "source_freshness IN ('current', 'stale', 'unavailable')",
            name="ck_cases_source_freshness",
        ),
        UniqueConstraint("organization_id", "id", name="uq_cases_org_id"),
        UniqueConstraint("organization_id", "public_id", name="uq_cases_org_public"),
        UniqueConstraint("organization_id", "source_id", name="uq_cases_org_source"),
        UniqueConstraint("legacy_task_id", name="uq_cases_legacy_task"),
        ForeignKeyConstraint(
            ["organization_id", "owner_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_cases_org_owner_memberships",
            ondelete="RESTRICT",
        ),
        Index("ix_cases_org_status_due", "organization_id", "status", "due_at"),
        Index("ix_cases_org_updated", "organization_id", "updated_at"),
        Index("ix_cases_org_due_public", "organization_id", "due_at", "public_id"),
        Index(
            "ix_cases_org_updated_public",
            "organization_id",
            text("updated_at DESC"),
            "public_id",
        ),
        Index(
            "ix_cases_org_priority_queue",
            "organization_id",
            text(
                "(\n"
                "CASE\n"
                "    WHEN risk::text = 'high'::text THEN 0\n"
                "    WHEN risk::text = 'medium'::text THEN 1\n"
                "    ELSE 2\n"
                "END)"
            ),
            "due_at",
            "public_id",
        ),
        Index(
            "ix_cases_public_id_trgm",
            "public_id",
            postgresql_using="gin",
            postgresql_ops={"public_id": "gin_trgm_ops"},
        ),
        Index(
            "ix_cases_external_reference_trgm",
            "external_reference",
            postgresql_using="gin",
            postgresql_ops={"external_reference": "gin_trgm_ops"},
        ),
        Index(
            "ix_cases_issue_trgm",
            "issue",
            postgresql_using="gin",
            postgresql_ops={"issue": "gin_trgm_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    legacy_task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="RESTRICT")
    )
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    external_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    issue: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    urgency: Mapped[str] = mapped_column(String(16), nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    impact_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    impact_currency: Mapped[str | None] = mapped_column(String(3))
    source_freshness: Mapped[str] = mapped_column(String(16), nullable=False)
    source_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class CaseRequestModel(Base):
    __tablename__ = "case_requests"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('email', 'chat', 'phone', 'webhook')", name="ck_case_requests_channel"
        ),
        UniqueConstraint("organization_id", "case_id", name="uq_case_requests_org_case"),
        UniqueConstraint("organization_id", "public_id", name="uq_case_requests_org_public"),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_requests_org_case",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_message: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CaseCustomerModel(Base):
    __tablename__ = "case_customers"
    __table_args__ = (
        CheckConstraint("tier IN ('standard', 'vip', 'enterprise')", name="ck_case_customers_tier"),
        UniqueConstraint("organization_id", "case_id", name="uq_case_customers_org_case"),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_customers_org_case",
            ondelete="CASCADE",
        ),
        Index(
            "ix_case_customers_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    locale: Mapped[str] = mapped_column(String(35), nullable=False)
    contact: Mapped[str] = mapped_column(String(320), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class BusinessObjectSnapshotModel(Base):
    __tablename__ = "business_object_snapshots"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_business_snapshots_version_positive"),
        CheckConstraint(
            "object_type IN ('invoice', 'payment', 'subscription', 'account', 'order', "
            "'delivery', 'other')",
            name="ck_business_snapshots_type",
        ),
        CheckConstraint(
            "source_freshness IN ('current', 'stale', 'unavailable')",
            name="ck_business_snapshots_freshness",
        ),
        UniqueConstraint("organization_id", "id", name="uq_business_snapshots_org_id"),
        UniqueConstraint(
            "organization_id", "case_id", "id", name="uq_business_snapshots_org_case_id"
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_business_snapshots_org_public"),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_business_snapshots_org_case",
            ondelete="CASCADE",
        ),
        Index("ix_business_snapshots_org_case", "organization_id", "case_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_freshness: Mapped[str] = mapped_column(String(16), nullable=False)
    source_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ConversationThreadModel(Base):
    __tablename__ = "conversation_threads"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_conversation_threads_version_positive"),
        UniqueConstraint("organization_id", "id", name="uq_conversation_threads_org_id"),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "id",
            name="uq_conversation_threads_org_case_id",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_conversation_threads_org_public"),
        UniqueConstraint("organization_id", "case_id", name="uq_conversation_threads_org_case"),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_conversation_threads_org_case",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ConversationMessageModel(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_conversation_messages_version_positive"),
        CheckConstraint(
            "author_type IN ('customer', 'member', 'system')",
            name="ck_conversation_messages_author_type",
        ),
        CheckConstraint(
            "channel IN ('email', 'chat', 'phone', 'webhook', 'internal_note')",
            name="ck_conversation_messages_channel",
        ),
        CheckConstraint(
            "(channel = 'internal_note' AND internal) OR "
            "(channel <> 'internal_note' AND NOT internal)",
            name="ck_conversation_messages_internal",
        ),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_conversation_messages_org_public"
        ),
        UniqueConstraint(
            "organization_id", "id", name="uq_conversation_messages_org_id"
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_conversation_messages_org_case",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "thread_id"],
            [
                "conversation_threads.organization_id",
                "conversation_threads.case_id",
                "conversation_threads.id",
            ],
            name="fk_conversation_messages_org_thread",
            ondelete="CASCADE",
        ),
        Index("ix_conversation_messages_org_case", "organization_id", "case_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    thread_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    author_type: Mapped[str] = mapped_column(String(16), nullable=False)
    author_id: Mapped[str | None] = mapped_column(String(64))
    author_name: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    internal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ResponseDraftModel(Base):
    __tablename__ = "response_drafts"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_response_drafts_version_positive"),
        CheckConstraint(
            "status IN ('draft', 'ready', 'blocked')", name="ck_response_drafts_status"
        ),
        UniqueConstraint("organization_id", "case_id", name="uq_response_drafts_org_case"),
        UniqueConstraint("organization_id", "id", name="uq_response_drafts_org_id"),
        UniqueConstraint("organization_id", "public_id", name="uq_response_drafts_org_public"),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_response_drafts_org_case",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
