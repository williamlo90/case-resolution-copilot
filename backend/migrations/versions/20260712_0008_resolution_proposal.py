"""Add support resolution proposal fields.

Revision ID: 20260712_0008
Revises: 20260712_0007
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260712_0008"
down_revision: str | None = "20260712_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "proposal_versions",
        sa.Column(
            "proposal_type", sa.String(32), nullable=False, server_default="support_resolution"
        ),
    )
    op.add_column(
        "proposal_versions",
        sa.Column(
            "proposed_outcome", sa.String(64), nullable=False, server_default="manual_review"
        ),
    )
    op.add_column(
        "proposal_versions",
        sa.Column("action_type", sa.String(64), nullable=False, server_default="escalate_case"),
    )
    op.add_column(
        "proposal_versions",
        sa.Column("rationale", sa.Text(), nullable=False, server_default="Migrated proposal"),
    )
    op.add_column(
        "proposal_versions",
        sa.Column(
            "draft_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "proposal_versions",
        sa.Column("policy_version", sa.String(64), nullable=False, server_default="legacy-policy"),
    )
    for column in (
        "proposal_type",
        "proposed_outcome",
        "action_type",
        "rationale",
        "draft_response",
        "policy_version",
    ):
        op.alter_column("proposal_versions", column, server_default=None)


def downgrade() -> None:
    for column in (
        "policy_version",
        "draft_response",
        "rationale",
        "action_type",
        "proposed_outcome",
        "proposal_type",
    ):
        op.drop_column("proposal_versions", column)
