"""Add indexes for stable case queue keyset pagination.

Revision ID: 20260730_0018
Revises: 20260728_0017
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0018"
down_revision: str | None = "20260728_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_cases_org_due_public",
        "cases",
        ["organization_id", "due_at", "public_id"],
    )
    op.create_index(
        "ix_cases_org_updated_public",
        "cases",
        ["organization_id", sa.text("updated_at DESC"), "public_id"],
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX ix_cases_org_priority_queue
            ON cases (
                organization_id,
                (CASE
                    WHEN risk = 'high' THEN 0
                    WHEN risk = 'medium' THEN 1
                    ELSE 2
                END),
                due_at,
                public_id
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_cases_org_priority_queue", table_name="cases")
    op.drop_index("ix_cases_org_updated_public", table_name="cases")
    op.drop_index("ix_cases_org_due_public", table_name="cases")
