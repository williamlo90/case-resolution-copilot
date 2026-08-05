"""Add versioned policy retrieval and immutable evidence.

Revision ID: 20260705_0005
Revises: 20260704_0004
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "20260705_0005"
down_revision: str | None = "20260704_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.drop_constraint("ck_proposal_versions_status", "proposal_versions", type_="check")
    op.create_check_constraint(
        "ck_proposal_versions_status",
        "proposal_versions",
        "status IN ('draft_waiting_evidence', 'waiting_approval')",
    )
    op.create_table(
        "policy_document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("carrier", sa.String(120), nullable=False),
        sa.Column("product", sa.String(32), nullable=False),
        sa.Column("jurisdiction", sa.String(16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("lifecycle_status", sa.String(16), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("corpus_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "lifecycle_status IN ('active', 'quarantined')",
            name="ck_policy_lifecycle_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "version", name="uq_policy_source_version"),
    )
    op.create_table(
        "policy_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("chunking_version", sa.String(64), nullable=False),
        sa.Column("embedding_version", sa.String(64), nullable=False),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("embedding", VECTOR(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["policy_version_id"], ["policy_document_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_version_id", "clause", name="uq_policy_chunk_clause"
        ),
    )
    op.create_table(
        "retrieval_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("clause", sa.String(64), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("retrieval_score", sa.Float(), nullable=False),
        sa.Column("corpus_version", sa.String(64), nullable=False),
        sa.Column("chunking_version", sa.String(64), nullable=False),
        sa.Column("embedding_version", sa.String(64), nullable=False),
        sa.Column("index_version", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["policy_chunks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["policy_version_id"], ["policy_document_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["proposal_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", "chunk_id", name="uq_evidence_proposal_chunk"),
    )


def downgrade() -> None:
    op.drop_table("retrieval_evidence")
    op.drop_table("policy_chunks")
    op.drop_table("policy_document_versions")
    op.drop_constraint("ck_proposal_versions_status", "proposal_versions", type_="check")
    op.create_check_constraint(
        "ck_proposal_versions_status",
        "proposal_versions",
        "status = 'draft_waiting_evidence'",
    )
