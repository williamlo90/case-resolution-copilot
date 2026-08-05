from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class OrganizationSettingModel(Base):
    __tablename__ = "organization_settings"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_organization_settings_version"),
        CheckConstraint(
            "section IN ('general', 'approvals', 'notifications', 'security', 'retention')",
            name="ck_organization_settings_section",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_organization_settings_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "section",
            name="uq_organization_settings_org_section",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_settings_org",
            ondelete="CASCADE",
        ),
        Index(
            "ix_organization_settings_org_section",
            "organization_id",
            "section",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    section: Mapped[str] = mapped_column(String(32), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class NotificationModel(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_notifications_version"),
        CheckConstraint(
            "kind IN ('sla_risk', 'review_waiting', 'action_recovery', "
            "'membership_changed', 'settings_changed', 'system')",
            name="ck_notifications_kind",
        ),
        CheckConstraint(
            "status IN ('unread', 'read')",
            name="ck_notifications_status",
        ),
        CheckConstraint(
            "resource_type IN ('case', 'review', 'action', 'connection', "
            "'member', 'settings', 'system')",
            name="ck_notifications_resource_type",
        ),
        CheckConstraint(
            "(status = 'read' AND read_at IS NOT NULL) OR (status = 'unread' AND read_at IS NULL)",
            name="ck_notifications_read_state",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_notifications_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_notifications_org_id",
        ),
        UniqueConstraint(
            "organization_id",
            "recipient_id",
            "event_key",
            name="uq_notifications_org_recipient_event",
        ),
        ForeignKeyConstraint(
            ["organization_id", "recipient_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_notifications_org_recipient",
            ondelete="CASCADE",
        ),
        Index(
            "ix_notifications_org_recipient_status_created",
            "organization_id",
            "recipient_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    recipient_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    recipient_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationOutboxModel(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('in_app', 'email')",
            name="ck_notification_outbox_channel",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'skipped', 'failed')",
            name="ck_notification_outbox_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_notification_outbox_attempt_count",
        ),
        CheckConstraint(
            "(status = 'delivered' AND delivered_at IS NOT NULL) OR "
            "(status <> 'delivered' AND delivered_at IS NULL)",
            name="ck_notification_outbox_delivery_state",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_notification_outbox_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "notification_id",
            "channel",
            name="uq_notification_outbox_org_notification_channel",
        ),
        ForeignKeyConstraint(
            ["organization_id", "notification_id"],
            ["notifications.organization_id", "notifications.id"],
            name="fk_notification_outbox_org_notification",
            ondelete="CASCADE",
        ),
        Index(
            "ix_notification_outbox_org_status_available",
            "organization_id",
            "status",
            "available_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    notification_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    destination_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CaseDataGovernanceModel(Base):
    __tablename__ = "case_data_governance"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_case_data_governance_version"),
        CheckConstraint(
            "retention_policy_version > 0",
            name="ck_case_data_governance_policy_version",
        ),
        CheckConstraint(
            "redaction_status IN ('active', 'due', 'redacted', 'held')",
            name="ck_case_data_governance_redaction_status",
        ),
        CheckConstraint(
            "(redaction_status = 'redacted' AND redacted_at IS NOT NULL) OR "
            "(redaction_status <> 'redacted' AND redacted_at IS NULL)",
            name="ck_case_data_governance_redacted_at",
        ),
        CheckConstraint(
            "(legal_hold AND redaction_status = 'held') OR "
            "(NOT legal_hold AND redaction_status <> 'held')",
            name="ck_case_data_governance_legal_hold",
        ),
        CheckConstraint(
            "audit_retention_until >= conversation_retention_until",
            name="ck_case_data_governance_retention_order",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_data_governance_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            name="uq_case_data_governance_org_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_data_governance_org_case",
            ondelete="CASCADE",
        ),
        Index(
            "ix_case_data_governance_org_status_due",
            "organization_id",
            "redaction_status",
            "conversation_retention_until",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    retention_policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation_retention_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    audit_retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redaction_status: Mapped[str] = mapped_column(String(16), nullable=False)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class CaseQualityProjectionModel(Base):
    __tablename__ = "case_quality_projections"
    __table_args__ = (
        CheckConstraint(
            "category IN ('decision_quality', 'safety', 'reliability')",
            name="ck_case_quality_projections_category",
        ),
        CheckConstraint(
            "result IN ('passed', 'needs_attention')",
            name="ck_case_quality_projections_result",
        ),
        CheckConstraint(
            "source IN ('deterministic_demo', 'manual', 'imported')",
            name="ck_case_quality_projections_source",
        ),
        CheckConstraint(
            "version > 0",
            name="ck_case_quality_projections_version",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_quality_projections_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "category",
            name="uq_case_quality_projections_org_case_category",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_quality_projections_org_case",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "evaluated_by_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_quality_projections_org_evaluator",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_case_quality_projections_org_category_result",
            "organization_id",
            "category",
            "result",
            "evaluated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    scenario: Mapped[str] = mapped_column(String(300), nullable=False)
    expected_decision: Mapped[str] = mapped_column(String(300), nullable=False)
    observed_decision: Mapped[str] = mapped_column(String(300), nullable=False)
    policy_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    policy_evidence_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    customer_or_business_impact: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluated_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    evaluated_by_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluated_by_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
