"""Align policy category storage with the application contract.

Revision ID: 20260728_0017
Revises: 20260728_0016
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0017"
down_revision: str | None = "20260728_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "policy_document_versions",
        "case_category",
        existing_type=sa.String(length=120),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "policy_document_versions",
        "case_category",
        existing_type=sa.String(length=64),
        type_=sa.String(length=120),
        existing_nullable=False,
    )
