"""Add tenant-scoped operational controls and quality projections.

Revision ID: 20260723_0015
Revises: 20260723_0014
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0015"
down_revision: str | None = "20260723_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.String(length=32), nullable=False),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_organization_settings_version",
        ),
        sa.CheckConstraint(
            "section IN ('general', 'approvals', 'notifications', 'security', 'retention')",
            name="ck_organization_settings_section",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_settings_org",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_organization_settings_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "section",
            name="uq_organization_settings_org_section",
        ),
    )
    op.create_index(
        "ix_organization_settings_org_section",
        "organization_settings",
        ["organization_id", "section"],
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_public_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_public_id", sa.String(length=64), nullable=False),
        sa.Column("event_key", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_notifications_version"),
        sa.CheckConstraint(
            "kind IN ('sla_risk', 'review_waiting', 'action_recovery', "
            "'membership_changed', 'settings_changed', 'system')",
            name="ck_notifications_kind",
        ),
        sa.CheckConstraint(
            "status IN ('unread', 'read')",
            name="ck_notifications_status",
        ),
        sa.CheckConstraint(
            "resource_type IN ('case', 'review', 'action', 'connection', "
            "'member', 'settings', 'system')",
            name="ck_notifications_resource_type",
        ),
        sa.CheckConstraint(
            "(status = 'read' AND read_at IS NOT NULL) OR "
            "(status = 'unread' AND read_at IS NULL)",
            name="ck_notifications_read_state",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "recipient_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_notifications_org_recipient",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_notifications_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_notifications_org_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "recipient_id",
            "event_key",
            name="uq_notifications_org_recipient_event",
        ),
    )
    op.create_index(
        "ix_notifications_org_recipient_status_created",
        "notifications",
        ["organization_id", "recipient_id", "status", "created_at"],
    )

    op.create_table(
        "notification_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("destination_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "channel IN ('in_app', 'email')",
            name="ck_notification_outbox_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'skipped', 'failed')",
            name="ck_notification_outbox_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_notification_outbox_attempt_count",
        ),
        sa.CheckConstraint(
            "(status = 'delivered' AND delivered_at IS NOT NULL) OR "
            "(status <> 'delivered' AND delivered_at IS NULL)",
            name="ck_notification_outbox_delivery_state",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "notification_id"],
            ["notifications.organization_id", "notifications.id"],
            name="fk_notification_outbox_org_notification",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_notification_outbox_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "notification_id",
            "channel",
            name="uq_notification_outbox_org_notification_channel",
        ),
    )
    op.create_index(
        "ix_notification_outbox_org_status_available",
        "notification_outbox",
        ["organization_id", "status", "available_at"],
    )

    op.create_table(
        "case_data_governance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retention_policy_version", sa.Integer(), nullable=False),
        sa.Column(
            "conversation_retention_until",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "audit_retention_until",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("redaction_status", sa.String(length=16), nullable=False),
        sa.Column(
            "legal_hold",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("redacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_case_data_governance_version",
        ),
        sa.CheckConstraint(
            "retention_policy_version > 0",
            name="ck_case_data_governance_policy_version",
        ),
        sa.CheckConstraint(
            "redaction_status IN ('active', 'due', 'redacted', 'held')",
            name="ck_case_data_governance_redaction_status",
        ),
        sa.CheckConstraint(
            "(redaction_status = 'redacted' AND redacted_at IS NOT NULL) OR "
            "(redaction_status <> 'redacted' AND redacted_at IS NULL)",
            name="ck_case_data_governance_redacted_at",
        ),
        sa.CheckConstraint(
            "(legal_hold AND redaction_status = 'held') OR "
            "(NOT legal_hold AND redaction_status <> 'held')",
            name="ck_case_data_governance_legal_hold",
        ),
        sa.CheckConstraint(
            "audit_retention_until >= conversation_retention_until",
            name="ck_case_data_governance_retention_order",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_data_governance_org_case",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_data_governance_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            name="uq_case_data_governance_org_case",
        ),
    )
    op.create_index(
        "ix_case_data_governance_org_status_due",
        "case_data_governance",
        ["organization_id", "redaction_status", "conversation_retention_until"],
    )

    op.create_table(
        "case_quality_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_public_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("scenario", sa.String(length=300), nullable=False),
        sa.Column("expected_decision", sa.String(length=300), nullable=False),
        sa.Column("observed_decision", sa.String(length=300), nullable=False),
        sa.Column("policy_evidence", sa.Text(), nullable=False),
        sa.Column("policy_evidence_present", sa.Boolean(), nullable=False),
        sa.Column("customer_or_business_impact", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("evaluated_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluated_by_public_id", sa.String(length=64), nullable=False),
        sa.Column("evaluated_by_name", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "category IN ('decision_quality', 'safety', 'reliability')",
            name="ck_case_quality_projections_category",
        ),
        sa.CheckConstraint(
            "result IN ('passed', 'needs_attention')",
            name="ck_case_quality_projections_result",
        ),
        sa.CheckConstraint(
            "source IN ('deterministic_demo', 'manual', 'imported')",
            name="ck_case_quality_projections_source",
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_case_quality_projections_version",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_quality_projections_org_case",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "evaluated_by_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_quality_projections_org_evaluator",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_quality_projections_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "category",
            name="uq_case_quality_projections_org_case_category",
        ),
    )
    op.create_index(
        "ix_case_quality_projections_org_category_result",
        "case_quality_projections",
        ["organization_id", "category", "result", "evaluated_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    populated = connection.scalar(
        sa.text(
            """
            SELECT
                (SELECT count(*) FROM organization_settings)
              + (SELECT count(*) FROM notifications)
              + (SELECT count(*) FROM notification_outbox)
              + (SELECT count(*) FROM case_data_governance)
              + (SELECT count(*) FROM case_quality_projections)
            """
        )
    )
    if populated:
        raise RuntimeError("Refusing to drop populated B7 operational-control data.")

    op.drop_index(
        "ix_case_quality_projections_org_category_result",
        table_name="case_quality_projections",
    )
    op.drop_table("case_quality_projections")
    op.drop_index(
        "ix_case_data_governance_org_status_due",
        table_name="case_data_governance",
    )
    op.drop_table("case_data_governance")
    op.drop_index(
        "ix_notification_outbox_org_status_available",
        table_name="notification_outbox",
    )
    op.drop_table("notification_outbox")
    op.drop_index(
        "ix_notifications_org_recipient_status_created",
        table_name="notifications",
    )
    op.drop_table("notifications")
    op.drop_index(
        "ix_organization_settings_org_section",
        table_name="organization_settings",
    )
    op.drop_table("organization_settings")
