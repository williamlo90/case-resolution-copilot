"""Replace travel policy metadata with support policy metadata.

Revision ID: 20260712_0007
Revises: 20260705_0006
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260712_0007"
down_revision: str | None = "20260705_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("policy_document_versions", "carrier", new_column_name="case_category")
    op.alter_column("policy_document_versions", "product", new_column_name="plan")
    op.add_column(
        "policy_document_versions",
        sa.Column("customer_tier", sa.String(16), nullable=False, server_default="all"),
    )
    op.alter_column("policy_document_versions", "customer_tier", server_default=None)


def downgrade() -> None:
    op.drop_column("policy_document_versions", "customer_tier")
    op.alter_column("policy_document_versions", "plan", new_column_name="product")
    op.alter_column("policy_document_versions", "case_category", new_column_name="carrier")
