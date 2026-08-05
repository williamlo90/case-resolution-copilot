"""Add tenant-scoped governed policies and case evidence.

Revision ID: 20260722_0011
Revises: 20260722_0010
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0011"
down_revision: str | None = "20260722_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_name", sa.String(length=500), nullable=False),
        sa.Column("source_error", sa.Text(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("current_version >= 0", name="ck_policies_current_version"),
        sa.CheckConstraint("version > 0", name="ck_policies_version_positive"),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'published', 'scheduled', 'retired', "
            "'expired', 'conflicting', 'parsing_failed')",
            name="ck_policies_status",
        ),
        sa.CheckConstraint(
            "source_kind IN ('upload', 'url', 'manual')", name="ck_policies_source_kind"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_policies_org_owner_memberships",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_policies_org_id"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_policies_org_public"),
    )
    op.create_index(
        "ix_policies_org_status_updated",
        "policies",
        ["organization_id", "status", "updated_at"],
    )

    op.create_table(
        "governed_policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legacy_policy_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("decision_scope", sa.String(length=100), nullable=False),
        sa.Column("case_categories", postgresql.JSONB(), nullable=False),
        sa.Column("products", postgresql.JSONB(), nullable=False),
        sa.Column("regions", postgresql.JSONB(), nullable=False),
        sa.Column("channels", postgresql.JSONB(), nullable=False),
        sa.Column("customer_tiers", postgresql.JSONB(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name="ck_governed_policy_versions_version"),
        sa.CheckConstraint("record_version > 0", name="ck_governed_policy_versions_record_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'published', 'scheduled', 'retired')",
            name="ck_governed_policy_versions_status",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from",
            name="ck_governed_policy_versions_effective_order",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "policy_id"],
            ["policies.organization_id", "policies.id"],
            name="fk_governed_versions_org_policy",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_policy_version_id"],
            ["policy_document_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "policy_id",
            "version",
            name="uq_governed_versions_org_policy_version",
        ),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_governed_versions_org_public"),
        sa.UniqueConstraint(
            "organization_id",
            "policy_id",
            "id",
            name="uq_governed_versions_org_policy_id",
        ),
        sa.UniqueConstraint("legacy_policy_version_id", name="uq_governed_versions_legacy_version"),
    )
    op.create_index(
        "ix_governed_versions_org_status_effective",
        "governed_policy_versions",
        ["organization_id", "status", "effective_from"],
    )

    op.create_table(
        "governed_policy_clauses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("applies_when", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chunking_version", sa.String(length=64), nullable=False),
        sa.Column("embedding_version", sa.String(length=64), nullable=False),
        sa.Column("index_version", sa.String(length=64), nullable=False),
        sa.Column("embedding", VECTOR(32), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_governed_policy_clauses_sequence"),
        sa.ForeignKeyConstraint(
            ["organization_id", "policy_id", "policy_version_id"],
            [
                "governed_policy_versions.organization_id",
                "governed_policy_versions.policy_id",
                "governed_policy_versions.id",
            ],
            name="fk_governed_clauses_org_policy_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_governed_clauses_org_public"),
        sa.UniqueConstraint(
            "organization_id",
            "policy_version_id",
            "sequence",
            name="uq_governed_clauses_org_version_sequence",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "policy_id",
            "policy_version_id",
            "id",
            name="uq_governed_clauses_org_policy_version_id",
        ),
    )

    op.create_table(
        "case_policy_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("citation", sa.String(length=500), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("applicability", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("freshness", sa.String(length=16), nullable=False),
        sa.Column("conflict_state", sa.String(length=16), nullable=False),
        sa.Column("retrieval_score", sa.Float(), nullable=False),
        sa.Column("policy_content_hash", sa.String(length=64), nullable=False),
        sa.Column("clause_content_hash", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("corpus_version", sa.String(length=64), nullable=False),
        sa.Column("chunking_version", sa.String(length=64), nullable=False),
        sa.Column("embedding_version", sa.String(length=64), nullable=False),
        sa.Column("index_version", sa.String(length=64), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "freshness IN ('current', 'stale')", name="ck_case_policy_evidence_freshness"
        ),
        sa.CheckConstraint(
            "conflict_state IN ('none', 'possible', 'confirmed')",
            name="ck_case_policy_evidence_conflict",
        ),
        sa.CheckConstraint(
            "retrieval_score >= -1 AND retrieval_score <= 1",
            name="ck_case_policy_evidence_score",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_policy_evidence_org_case",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "policy_id"],
            ["policies.organization_id", "policies.id"],
            name="fk_case_policy_evidence_org_policy",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "policy_id", "policy_version_id"],
            [
                "governed_policy_versions.organization_id",
                "governed_policy_versions.policy_id",
                "governed_policy_versions.id",
            ],
            name="fk_case_policy_evidence_org_policy_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "policy_id", "policy_version_id", "clause_id"],
            [
                "governed_policy_clauses.organization_id",
                "governed_policy_clauses.policy_id",
                "governed_policy_clauses.policy_version_id",
                "governed_policy_clauses.id",
            ],
            name="fk_case_policy_evidence_org_clause",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_case_policy_evidence_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "fingerprint",
            name="uq_case_policy_evidence_org_case_fingerprint",
        ),
    )
    op.create_index(
        "ix_case_policy_evidence_org_case_recorded",
        "case_policy_evidence",
        ["organization_id", "case_id", "recorded_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    policy_count = connection.scalar(sa.text("SELECT count(*) FROM policies"))
    if policy_count:
        raise RuntimeError("Refusing to drop populated B3 governed policy data.")

    op.drop_index("ix_case_policy_evidence_org_case_recorded", table_name="case_policy_evidence")
    op.drop_table("case_policy_evidence")
    op.drop_table("governed_policy_clauses")
    op.drop_index(
        "ix_governed_versions_org_status_effective", table_name="governed_policy_versions"
    )
    op.drop_table("governed_policy_versions")
    op.drop_index("ix_policies_org_status_updated", table_name="policies")
    op.drop_table("policies")
