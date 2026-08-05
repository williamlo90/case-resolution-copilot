"""Add version-bound reviewer reservations and approval decisions.

Revision ID: 20260705_0006
Revises: 20260705_0005
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260705_0006"
down_revision: str | None = "20260705_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reviewer_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("reviewer_role", sa.String(32), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'consumed', 'expired')",
            name="ck_reviewer_reservations_status",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["proposal_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_reviewer_reservations_active_proposal",
        "reviewer_reservations",
        ["proposal_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "approval_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("reviewer_role", sa.String(32), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('approved', 'rejected', 'needs_information')",
            name="ck_approval_decisions_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["proposal_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reviewer_reservations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", name="uq_approval_decisions_proposal"),
        sa.UniqueConstraint("reservation_id", name="uq_approval_decisions_reservation"),
    )


def downgrade() -> None:
    op.drop_table("approval_decisions")
    op.drop_index(
        "uq_reviewer_reservations_active_proposal",
        table_name="reviewer_reservations",
    )
    op.drop_table("reviewer_reservations")
