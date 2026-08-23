"""Add bounded inbox sync and draft delivery state.

Revision ID: 20260813_0023
Revises: 20260813_0022
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0023"
down_revision: str | None = "20260813_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_sync_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_history_id", sa.String(length=500), nullable=True),
        sa.Column("last_observed_history_id", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_recovery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="ck_inbox_checkpoints_version"),
        sa.CheckConstraint(
            "status IN ('current', 'syncing', 'delayed', 'failed', 'reauthorize')",
            name="ck_inbox_checkpoints_status",
        ),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name="ck_inbox_checkpoints_failure_count",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_inbox_checkpoints_org_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "connection_id",
            name="uq_inbox_checkpoints_org_connection",
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_inbox_checkpoints_org_public"
        ),
    )

    op.create_table(
        "inbox_sync_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("trigger_key", sa.String(length=200), nullable=False),
        sa.Column("requested_history_id", sa.String(length=500), nullable=True),
        sa.Column("page_token", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("page_budget", sa.Integer(), nullable=False),
        sa.Column("item_budget", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "trigger IN ('connect', 'manual', 'schedule', 'push', 'recovery')",
            name="ck_inbox_sync_jobs_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'dead')",
            name="ck_inbox_sync_jobs_status",
        ),
        sa.CheckConstraint(
            "page_budget BETWEEN 1 AND 10", name="ck_inbox_sync_jobs_pages"
        ),
        sa.CheckConstraint(
            "item_budget BETWEEN 1 AND 100", name="ck_inbox_sync_jobs_items"
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_inbox_sync_jobs_attempts"),
        sa.CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR (status <> 'running')",
            name="ck_inbox_sync_jobs_running_lease",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_inbox_sync_jobs_org_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_inbox_sync_jobs_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "connection_id",
            "trigger_key",
            name="uq_inbox_sync_jobs_org_trigger",
        ),
    )
    op.create_index(
        "ix_inbox_sync_jobs_claim",
        "inbox_sync_jobs",
        ["status", "available_at", "lease_expires_at"],
    )

    op.create_table(
        "inbox_draft_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "external_conversation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response_draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response_draft_version", sa.Integer(), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("policy_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("conversation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("provider_thread_id", sa.String(length=500), nullable=False),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject_snapshot", sa.String(length=300), nullable=False),
        sa.Column("body_hash", sa.String(length=64), nullable=False),
        sa.Column("in_reply_to", sa.String(length=1000), nullable=True),
        sa.Column("references", postgresql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_draft_id", sa.String(length=500), nullable=True),
        sa.Column("provider_message_id", sa.String(length=500), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ready', 'running', 'completed', 'failed_safe', "
            "'outcome_unknown', 'recovery_required')",
            name="ck_inbox_draft_deliveries_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_inbox_draft_deliveries_attempts"
        ),
        sa.CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR (status <> 'running')",
            name="ck_inbox_draft_deliveries_running_lease",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_inbox_draft_deliveries_org_case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "external_conversation_id"],
            ["external_conversations.organization_id", "external_conversations.id"],
            name="fk_inbox_draft_deliveries_org_conversation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_inbox_draft_deliveries_org_connection",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "response_draft_id"],
            ["response_drafts.organization_id", "response_drafts.id"],
            name="fk_inbox_draft_deliveries_org_response_draft",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_inbox_draft_deliveries_org_review",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_inbox_draft_deliveries_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_inbox_draft_deliveries_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_inbox_draft_deliveries_org_idempotency",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "response_draft_id",
            "response_draft_version",
            "decision_fingerprint",
            name="uq_inbox_draft_deliveries_authorized_snapshot",
        ),
    )
    op.create_index(
        "ix_inbox_draft_deliveries_org_status",
        "inbox_draft_deliveries",
        ["organization_id", "status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inbox_draft_deliveries_org_status",
        table_name="inbox_draft_deliveries",
    )
    op.drop_table("inbox_draft_deliveries")
    op.drop_index("ix_inbox_sync_jobs_claim", table_name="inbox_sync_jobs")
    op.drop_table("inbox_sync_jobs")
    op.drop_table("inbox_sync_checkpoints")
