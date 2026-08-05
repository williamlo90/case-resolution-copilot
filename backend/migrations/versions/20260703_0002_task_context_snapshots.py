"""Add task read fields and immutable context snapshots.

Revision ID: 20260703_0002
Revises: 20260703_0001
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260703_0002"
down_revision: str | None = "20260703_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "summary", sa.String(length=240), server_default="Refund request", nullable=False
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "due_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP + INTERVAL '60 minutes'"),
            nullable=False,
        ),
    )
    op.add_column("tasks", sa.Column("exposure_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("tasks", sa.Column("exposure_currency", sa.String(length=3), nullable=True))

    op.create_table(
        "customer_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("contact", sa.String(length=254), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_customer_snapshots_task_id"),
    )
    op.create_table(
        "booking_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=False),
        sa.Column("service_date_label", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("itinerary", sa.String(length=240), nullable=False),
        sa.Column("passengers", sa.Integer(), nullable=False),
        sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_booking_snapshots_task_id"),
    )


def downgrade() -> None:
    op.drop_table("booking_snapshots")
    op.drop_table("customer_snapshots")
    op.drop_column("tasks", "exposure_currency")
    op.drop_column("tasks", "exposure_amount")
    op.drop_column("tasks", "due_at")
    op.drop_column("tasks", "summary")
