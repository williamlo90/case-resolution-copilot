from datetime import datetime
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


class InboxSyncCheckpointModel(Base):
    __tablename__ = "inbox_sync_checkpoints"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_inbox_checkpoints_version"),
        CheckConstraint(
            "status IN ('current', 'syncing', 'delayed', 'failed', 'reauthorize')",
            name="ck_inbox_checkpoints_status",
        ),
        CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_inbox_checkpoints_failure_count",
        ),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            name="uq_inbox_checkpoints_org_connection",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_inbox_checkpoints_org_public",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_inbox_checkpoints_org_connection",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider_history_id: Mapped[str | None] = mapped_column(String(500))
    last_observed_history_id: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_recovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class InboxSyncJobModel(Base):
    __tablename__ = "inbox_sync_jobs"
    __table_args__ = (
        CheckConstraint(
            "trigger IN ('connect', 'manual', 'schedule', 'push', 'recovery')",
            name="ck_inbox_sync_jobs_trigger",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'dead')",
            name="ck_inbox_sync_jobs_status",
        ),
        CheckConstraint("page_budget BETWEEN 1 AND 10", name="ck_inbox_sync_jobs_pages"),
        CheckConstraint("item_budget BETWEEN 1 AND 100", name="ck_inbox_sync_jobs_items"),
        CheckConstraint("attempt_count >= 0", name="ck_inbox_sync_jobs_attempts"),
        CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'running')",
            name="ck_inbox_sync_jobs_running_lease",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_inbox_sync_jobs_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            "trigger_key",
            name="uq_inbox_sync_jobs_org_trigger",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_inbox_sync_jobs_org_connection",
            ondelete="CASCADE",
        ),
        Index(
            "ix_inbox_sync_jobs_claim",
            "status",
            "available_at",
            "lease_expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger_key: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_history_id: Mapped[str | None] = mapped_column(String(500))
    page_token: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    page_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    item_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class InboxDraftDeliveryModel(Base):
    __tablename__ = "inbox_draft_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'running', 'completed', 'failed_safe', "
            "'outcome_unknown', 'recovery_required')",
            name="ck_inbox_draft_deliveries_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_inbox_draft_deliveries_attempts",
        ),
        CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (status <> 'running')",
            name="ck_inbox_draft_deliveries_running_lease",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_inbox_draft_deliveries_org_id",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_inbox_draft_deliveries_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_inbox_draft_deliveries_org_idempotency",
        ),
        UniqueConstraint(
            "organization_id",
            "response_draft_id",
            "response_draft_version",
            "decision_fingerprint",
            name="uq_inbox_draft_deliveries_authorized_snapshot",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_inbox_draft_deliveries_org_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "external_conversation_id"],
            ["external_conversations.organization_id", "external_conversations.id"],
            name="fk_inbox_draft_deliveries_org_conversation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_inbox_draft_deliveries_org_connection",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "response_draft_id"],
            ["response_drafts.organization_id", "response_drafts.id"],
            name="fk_inbox_draft_deliveries_org_response_draft",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_inbox_draft_deliveries_org_review",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_inbox_draft_deliveries_org_status",
            "organization_id",
            "status",
            "updated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    external_conversation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    response_draft_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    response_draft_version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    decision_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_thread_id: Mapped[str] = mapped_column(String(500), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    in_reply_to: Mapped[str | None] = mapped_column(String(1000))
    references: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_draft_id: Mapped[str | None] = mapped_column(String(500))
    provider_message_id: Mapped[str | None] = mapped_column(String(500))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
