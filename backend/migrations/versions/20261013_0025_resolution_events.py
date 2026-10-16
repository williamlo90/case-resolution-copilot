"""Append-only case resolution evidence; legacy rows are not backfilled as verified."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "20261013_0025"
down_revision: str | None = "20260813_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_resolution_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("command_id", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("previous_event_id", pg.UUID(as_uuid=True)),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("data", pg.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "case_id", "id", name="uq_resolution_event_scope"),
        sa.UniqueConstraint(
            "organization_id", "case_id", "command_id", name="uq_resolution_command"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "previous_event_id"],
            [
                "case_resolution_events.organization_id",
                "case_resolution_events.case_id",
                "case_resolution_events.id",
            ],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_resolution_case_time",
        "case_resolution_events",
        ["organization_id", "case_id", "occurred_at"],
    )


def downgrade() -> None:
    # Historical evidence must be exported before an explicitly authorized downgrade.
    op.drop_index("ix_resolution_case_time", table_name="case_resolution_events")
    op.drop_table("case_resolution_events")
