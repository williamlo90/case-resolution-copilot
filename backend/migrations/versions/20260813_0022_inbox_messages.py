"""Add tenant-scoped external conversation mappings.

Revision ID: 20260813_0022
Revises: 20260813_0021
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0022"
down_revision: str | None = "20260813_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_conversation_messages_org_id",
        "conversation_messages",
        ["organization_id", "id"],
    )
    op.create_unique_constraint(
        "uq_response_drafts_org_id",
        "response_drafts",
        ["organization_id", "id"],
    )
    op.create_table(
        "external_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_thread_id", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("first_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_provider_message_id", sa.String(length=500), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
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
        sa.CheckConstraint("version > 0", name="ck_external_conversations_version"),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_external_conversations_org_connection",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_external_conversations_org_case",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "thread_id"],
            ["conversation_threads.organization_id", "conversation_threads.id"],
            name="fk_external_conversations_org_thread",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_external_conversations_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_external_conversations_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "connection_id",
            "provider_thread_id",
            name="uq_external_conversations_org_provider_thread",
        ),
        sa.UniqueConstraint(
            "organization_id", "case_id", name="uq_external_conversations_org_case"
        ),
    )
    op.create_index(
        "ix_external_conversations_org_latest",
        "external_conversations",
        ["organization_id", "latest_message_at"],
    )

    op.create_table(
        "external_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "external_conversation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "conversation_message_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("provider_message_id", sa.String(length=500), nullable=False),
        sa.Column("rfc_message_id", sa.String(length=1000), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("sender", postgresql.JSONB(), nullable=False),
        sa.Column("recipients", postgresql.JSONB(), nullable=False),
        sa.Column("provider_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sanitized_content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_source_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("omission_reason", sa.String(length=500), nullable=True),
        sa.Column("attachment_count", sa.Integer(), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="ck_external_messages_direction",
        ),
        sa.CheckConstraint(
            "attachment_count >= 0", name="ck_external_messages_attachments"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_external_messages_org_connection",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "external_conversation_id"],
            ["external_conversations.organization_id", "external_conversations.id"],
            name="fk_external_messages_org_conversation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "conversation_message_id"],
            ["conversation_messages.organization_id", "conversation_messages.id"],
            name="fk_external_messages_org_local_message",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_external_messages_org_id"
        ),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_external_messages_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "connection_id",
            "provider_message_id",
            name="uq_external_messages_org_provider_message",
        ),
    )
    op.create_index(
        "ix_external_messages_org_conversation_received",
        "external_messages",
        ["organization_id", "external_conversation_id", "provider_received_at"],
    )

    op.create_table(
        "external_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_attachment_id", sa.String(length=500), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("reported_size", sa.Integer(), nullable=False),
        sa.Column("content_status", sa.String(length=32), nullable=False),
        sa.Column("local_evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("parser_status", sa.String(length=32), nullable=False),
        sa.Column("malware_scan_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("reported_size >= 0", name="ck_external_attachments_size"),
        sa.CheckConstraint(
            "content_status IN ('metadata_only', 'available', 'unsupported', "
            "'too_large', 'blocked', 'deleted')",
            name="ck_external_attachments_content_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "external_message_id"],
            ["external_messages.organization_id", "external_messages.id"],
            name="fk_external_attachments_org_message",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_external_attachments_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "external_message_id",
            "provider_attachment_id",
            name="uq_external_attachments_org_provider",
        ),
    )


def downgrade() -> None:
    op.drop_table("external_attachments")
    op.drop_index(
        "ix_external_messages_org_conversation_received",
        table_name="external_messages",
    )
    op.drop_table("external_messages")
    op.drop_index(
        "ix_external_conversations_org_latest",
        table_name="external_conversations",
    )
    op.drop_table("external_conversations")
    op.drop_constraint(
        "uq_response_drafts_org_id",
        "response_drafts",
        type_="unique",
    )
    op.drop_constraint(
        "uq_conversation_messages_org_id",
        "conversation_messages",
        type_="unique",
    )
