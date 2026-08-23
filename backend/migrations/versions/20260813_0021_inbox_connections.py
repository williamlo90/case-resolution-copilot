"""Add connected-inbox authorization state.

Revision ID: 20260813_0021
Revises: 20260805_0020
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0021"
down_revision: str | None = "20260805_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbox_connection_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_account_id", sa.String(length=500), nullable=False),
        sa.Column("account_address", sa.String(length=320), nullable=False),
        sa.Column("import_mode", sa.String(length=16), nullable=False),
        sa.Column("label_filter", postgresql.JSONB(), nullable=False),
        sa.Column("initial_window_days", sa.Integer(), nullable=False),
        sa.Column("initial_item_limit", sa.Integer(), nullable=False),
        sa.Column("watch_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="ck_inbox_profiles_version"),
        sa.CheckConstraint(
            "import_mode IN ('paused', 'manual', 'scheduled')",
            name="ck_inbox_profiles_import_mode",
        ),
        sa.CheckConstraint(
            "initial_window_days BETWEEN 1 AND 30",
            name="ck_inbox_profiles_window",
        ),
        sa.CheckConstraint(
            "initial_item_limit BETWEEN 1 AND 100",
            name="ck_inbox_profiles_item_limit",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_inbox_profiles_org_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_inbox_profiles_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_inbox_profiles_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id", "connection_id", name="uq_inbox_profiles_org_connection"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "provider_account_id",
            name="uq_inbox_profiles_org_provider_account",
        ),
    )
    op.create_index(
        "ix_inbox_profiles_org_mode",
        "inbox_connection_profiles",
        ["organization_id", "import_mode"],
    )

    op.create_table(
        "connection_credential_envelopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("authentication_tag", sa.String(length=64), nullable=False),
        sa.Column("key_id", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("granted_scopes", postgresql.JSONB(), nullable=False),
        sa.Column("credential_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "algorithm = 'AES-256-GCM'",
            name="ck_connection_credentials_algorithm",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_connection_credentials_org_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "connection_id",
            name="uq_connection_credentials_org_connection",
        ),
    )

    op.create_table(
        "inbox_oauth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("requested_capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("return_path", sa.String(length=500), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("verifier_ciphertext", sa.Text(), nullable=False),
        sa.Column("verifier_nonce", sa.String(length=64), nullable=False),
        sa.Column("verifier_authentication_tag", sa.String(length=64), nullable=False),
        sa.Column("verifier_key_id", sa.String(length=64), nullable=False),
        sa.Column("verifier_algorithm", sa.String(length=32), nullable=False),
        sa.Column("verifier_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_inbox_oauth_attempt_count"
        ),
        sa.CheckConstraint(
            "expires_at <= created_at + INTERVAL '10 minutes'",
            name="ck_inbox_oauth_lifetime",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_inbox_oauth_org_actor",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash", name="uq_inbox_oauth_state_hash"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_inbox_oauth_org_public"
        ),
    )
    op.create_index(
        "ix_inbox_oauth_expires",
        "inbox_oauth_sessions",
        ["expires_at", "consumed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_inbox_oauth_expires", table_name="inbox_oauth_sessions")
    op.drop_table("inbox_oauth_sessions")
    op.drop_table("connection_credential_envelopes")
    op.drop_index("ix_inbox_profiles_org_mode", table_name="inbox_connection_profiles")
    op.drop_table("inbox_connection_profiles")
