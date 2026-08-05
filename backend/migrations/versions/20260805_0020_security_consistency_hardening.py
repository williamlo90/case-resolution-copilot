"""Keep invitation authority inside the owning organization.

Revision ID: 20260805_0020
Revises: 20260730_0019
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260805_0020"
down_revision: str | None = "20260730_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "invitations_invited_by_id_fkey",
        "invitations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_invitations_org_inviter_membership",
        "invitations",
        "memberships",
        ["organization_id", "invited_by_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_invitations_org_inviter_membership",
        "invitations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "invitations_invited_by_id_fkey",
        "invitations",
        "memberships",
        ["invited_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
