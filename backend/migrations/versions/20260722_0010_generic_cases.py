"""Add tenant-scoped generic cases and conversations.

Revision ID: 20260722_0010
Revises: 20260722_0009
Create Date: 2026-07-22
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0010"
down_revision: str | None = "20260722_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column[datetime], sa.Column[datetime]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def upgrade() -> None:
    op.create_unique_constraint("uq_memberships_org_id", "memberships", ["organization_id", "id"])
    created_at, updated_at = _timestamps()
    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legacy_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", sa.String(length=200), nullable=False),
        sa.Column("external_reference", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("issue", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("urgency", sa.String(length=16), nullable=False),
        sa.Column("risk", sa.String(length=16), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("impact_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("impact_currency", sa.String(length=3), nullable=True),
        sa.Column("source_freshness", sa.String(length=16), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        created_at,
        updated_at,
        sa.CheckConstraint("version > 0", name="ck_cases_version_positive"),
        sa.CheckConstraint(
            "category IN ('billing_dispute', 'refund_request', 'account_access', "
            "'service_exception')",
            name="ck_cases_category",
        ),
        sa.CheckConstraint(
            "status IN ('new', 'investigating', 'information_needed', 'needs_review', "
            "'waiting_customer', 'in_progress', 'completed')",
            name="ck_cases_status",
        ),
        sa.CheckConstraint(
            "urgency IN ('low', 'medium', 'high', 'critical')", name="ck_cases_urgency"
        ),
        sa.CheckConstraint("risk IN ('low', 'medium', 'high')", name="ck_cases_risk"),
        sa.CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_cases_impact_pair",
        ),
        sa.CheckConstraint(
            "source_freshness IN ('current', 'stale', 'unavailable')",
            name="ck_cases_source_freshness",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["legacy_task_id"], ["tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_cases_org_owner_memberships",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_cases_org_id"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_cases_org_public"),
        sa.UniqueConstraint("organization_id", "source_id", name="uq_cases_org_source"),
        sa.UniqueConstraint("legacy_task_id", name="uq_cases_legacy_task"),
    )
    op.create_index("ix_cases_org_status_due", "cases", ["organization_id", "status", "due_at"])
    op.create_index("ix_cases_org_updated", "cases", ["organization_id", "updated_at"])

    op.create_table(
        "case_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("customer_message", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "channel IN ('email', 'chat', 'phone', 'webhook')", name="ck_case_requests_channel"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_requests_org_case",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "case_id", name="uq_case_requests_org_case"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_case_requests_org_public"),
    )
    op.create_table(
        "case_customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=35), nullable=False),
        sa.Column("contact", sa.String(length=320), nullable=False),
        sa.Column(
            "captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "tier IN ('standard', 'vip', 'enterprise')", name="ck_case_customers_tier"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_customers_org_case",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "case_id", name="uq_case_customers_org_case"),
    )
    op.create_table(
        "business_object_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_reference", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_freshness", sa.String(length=16), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("version > 0", name="ck_business_snapshots_version_positive"),
        sa.CheckConstraint(
            "object_type IN ('invoice', 'payment', 'subscription', 'account', 'order', "
            "'delivery', 'other')",
            name="ck_business_snapshots_type",
        ),
        sa.CheckConstraint(
            "source_freshness IN ('current', 'stale', 'unavailable')",
            name="ck_business_snapshots_freshness",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_business_snapshots_org_case",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_business_snapshots_org_id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_business_snapshots_org_public"
        ),
    )
    op.create_index(
        "ix_business_snapshots_org_case",
        "business_object_snapshots",
        ["organization_id", "case_id"],
    )
    op.create_table(
        "conversation_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_conversation_threads_version_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_conversation_threads_org_case",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_conversation_threads_org_id"),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "id",
            name="uq_conversation_threads_org_case_id",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_conversation_threads_org_public"
        ),
        sa.UniqueConstraint("organization_id", "case_id", name="uq_conversation_threads_org_case"),
    )
    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_type", sa.String(length=16), nullable=False),
        sa.Column("author_id", sa.String(length=64), nullable=True),
        sa.Column("author_name", sa.String(length=200), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("internal", sa.Boolean(), nullable=False),
        sa.Column("source_reference", sa.String(length=200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_conversation_messages_version_positive"),
        sa.CheckConstraint(
            "author_type IN ('customer', 'member', 'system')",
            name="ck_conversation_messages_author_type",
        ),
        sa.CheckConstraint(
            "channel IN ('email', 'chat', 'phone', 'webhook', 'internal_note')",
            name="ck_conversation_messages_channel",
        ),
        sa.CheckConstraint(
            "(channel = 'internal_note' AND internal) OR "
            "(channel <> 'internal_note' AND NOT internal)",
            name="ck_conversation_messages_internal",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_conversation_messages_org_case",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "thread_id"],
            [
                "conversation_threads.organization_id",
                "conversation_threads.case_id",
                "conversation_threads.id",
            ],
            name="fk_conversation_messages_org_thread",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_conversation_messages_org_public"
        ),
    )
    op.create_index(
        "ix_conversation_messages_org_case",
        "conversation_messages",
        ["organization_id", "case_id", "created_at"],
    )
    op.create_table(
        "response_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_response_drafts_version_positive"),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'blocked')", name="ck_response_drafts_status"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_response_drafts_org_case",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "case_id", name="uq_response_drafts_org_case"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_response_drafts_org_public"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    case_count = connection.scalar(sa.text("SELECT count(*) FROM cases"))
    if case_count:
        raise RuntimeError("Refusing to drop populated B2 generic case data.")

    op.drop_table("response_drafts")
    op.drop_index("ix_conversation_messages_org_case", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_table("conversation_threads")
    op.drop_index("ix_business_snapshots_org_case", table_name="business_object_snapshots")
    op.drop_table("business_object_snapshots")
    op.drop_table("case_customers")
    op.drop_table("case_requests")
    op.drop_index("ix_cases_org_updated", table_name="cases")
    op.drop_index("ix_cases_org_status_due", table_name="cases")
    op.drop_table("cases")
    op.drop_constraint("uq_memberships_org_id", "memberships", type_="unique")
