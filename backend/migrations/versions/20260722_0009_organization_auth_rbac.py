"""Add organization, membership, invitation, and audit scope.

Revision ID: 20260722_0009
Revises: 20260712_0008
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0009"
down_revision: str | None = "20260712_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_organizations_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_organizations_public_id"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_memberships_version_positive"),
        sa.CheckConstraint(
            "role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_memberships_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'invited', 'deactivated')",
            name="ck_memberships_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_memberships_org_public"),
        sa.UniqueConstraint("organization_id", "subject_id", name="uq_memberships_org_subject"),
        sa.UniqueConstraint("organization_id", "email", name="uq_memberships_org_email"),
    )
    op.create_index("ix_memberships_org_status", "memberships", ["organization_id", "status"])
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_invitations_version_positive"),
        sa.CheckConstraint(
            "role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_invitations_role",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="ck_invitations_status",
        ),
        sa.ForeignKeyConstraint(["invited_by_id"], ["memberships.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_invitations_org_public"),
    )
    op.create_index("ix_invitations_org_status", "invitations", ["organization_id", "status"])

    op.add_column(
        "audit_events",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("audit_events", sa.Column("actor_id", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("subject_type", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("subject_id", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("summary", sa.String(length=500), nullable=True))
    op.alter_column("audit_events", "task_id", existing_type=postgresql.UUID(), nullable=True)
    op.create_foreign_key(
        "fk_audit_events_organization_id_organizations",
        "audit_events",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_audit_events_org_occurred",
        "audit_events",
        ["organization_id", "occurred_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    organization_count = connection.scalar(sa.text("SELECT count(*) FROM organizations"))
    generic_audit_count = connection.scalar(
        sa.text(
            "SELECT count(*) FROM audit_events "
            "WHERE organization_id IS NOT NULL AND task_id IS NULL"
        )
    )
    if organization_count or generic_audit_count:
        raise RuntimeError("Refusing to drop populated B1 organization or audit data.")

    op.drop_index("ix_audit_events_org_occurred", table_name="audit_events")
    op.drop_constraint(
        "fk_audit_events_organization_id_organizations", "audit_events", type_="foreignkey"
    )
    op.alter_column("audit_events", "task_id", existing_type=postgresql.UUID(), nullable=False)
    for column in ("summary", "subject_id", "subject_type", "actor_id", "organization_id"):
        op.drop_column("audit_events", column)

    op.drop_index("ix_invitations_org_status", table_name="invitations")
    op.drop_table("invitations")
    op.drop_index("ix_memberships_org_status", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("organizations")
