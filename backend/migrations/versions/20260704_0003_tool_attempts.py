"""Add typed tool attempts and external receipts.

Revision ID: 20260704_0003
Revises: 20260703_0002
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260704_0003"
down_revision: str | None = "20260703_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("side_effect_state", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("request_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'rejected', 'uncertain')",
            name="ck_tool_attempts_outcome",
        ),
        sa.CheckConstraint(
            "side_effect_state IN ('not_attempted', 'none', 'confirmed', 'possible')",
            name="ck_tool_attempts_side_effect_state",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tool_attempts_run_started", "tool_attempts", ["run_id", "started_at"]
    )
    op.create_index(
        "ix_tool_attempts_idempotency",
        "tool_attempts",
        ["tool_name", "idempotency_key"],
    )
    op.create_table(
        "external_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("external_reference", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tool_attempt_id"], ["tool_attempts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "tool_name",
            "idempotency_key",
            name="uq_external_receipts_provider_tool_idempotency",
        ),
        sa.UniqueConstraint(
            "external_reference", name="uq_external_receipts_external_reference"
        ),
        sa.UniqueConstraint(
            "tool_attempt_id", name="uq_external_receipts_tool_attempt_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("external_receipts")
    op.drop_index("ix_tool_attempts_idempotency", table_name="tool_attempts")
    op.drop_index("ix_tool_attempts_run_started", table_name="tool_attempts")
    op.drop_table("tool_attempts")
