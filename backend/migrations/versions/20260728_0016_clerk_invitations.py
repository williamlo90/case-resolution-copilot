"""Link invitations and track runtime connection configuration.

Revision ID: 20260728_0016
Revises: 20260723_0015
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0016"
down_revision: str | None = "20260723_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "invitations",
        sa.Column("provider_invitation_id", sa.String(length=200), nullable=True),
    )
    op.create_unique_constraint(
        "uq_invitations_provider_invitation",
        "invitations",
        ["provider_invitation_id"],
    )
    op.add_column(
        "connections",
        sa.Column("runtime_config_fingerprint", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connections", "runtime_config_fingerprint")
    op.drop_constraint(
        "uq_invitations_provider_invitation",
        "invitations",
        type_="unique",
    )
    op.drop_column("invitations", "provider_invitation_id")
