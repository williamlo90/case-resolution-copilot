"""Add versioned policy embedding and hybrid retrieval state.

Revision ID: 20260813_0024
Revises: 20260813_0023
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0024"
down_revision: str | None = "20260813_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DETERMINISTIC_PROFILE_ID = "00000000-0000-0000-0000-000000000512"
OPENAI_PROFILE_ID = "00000000-0000-0000-0000-000000000513"


def upgrade() -> None:
    op.create_table(
        "policy_embedding_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_key", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("normalization_version", sa.String(length=64), nullable=False),
        sa.Column("chunking_version", sa.String(length=64), nullable=False),
        sa.Column("index_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expected_clause_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("indexed_clause_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("build_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by", sa.String(length=64), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "dimensions = 512", name="ck_policy_embedding_profiles_dimensions"
        ),
        sa.CheckConstraint(
            "status IN ('building', 'ready', 'active', 'retired', 'failed')",
            name="ck_policy_embedding_profiles_status",
        ),
        sa.CheckConstraint(
            "expected_clause_count >= 0 AND indexed_clause_count >= 0",
            name="ck_policy_embedding_profiles_counts",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_key", name="uq_policy_embedding_profiles_key"),
    )
    op.create_index(
        "uq_policy_embedding_profiles_active_environment",
        "policy_embedding_profiles",
        ["environment"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "governed_policy_clause_embeddings_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", VECTOR(512), nullable=False),
        sa.Column("provider_request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["policy_embedding_profiles.id"],
            name="fk_policy_clause_embeddings_v2_profile",
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
            name="fk_policy_clause_embeddings_v2_clause",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "clause_id",
            "profile_id",
            name="uq_policy_clause_embeddings_v2_org_clause_profile",
        ),
    )
    op.create_index(
        "ix_policy_clause_embeddings_v2_hnsw",
        "governed_policy_clause_embeddings_v2",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )
    op.create_index(
        "ix_policy_clause_embeddings_v2_tenant_profile",
        "governed_policy_clause_embeddings_v2",
        ["organization_id", "profile_id", "clause_id"],
    )

    op.create_table(
        "policy_index_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("job_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("page_budget", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("indexed_clause_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_clause_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending', 'running', 'completed', 'failed', 'dead')",
            name="ck_policy_index_jobs_status",
        ),
        sa.CheckConstraint(
            "page_budget BETWEEN 1 AND 32", name="ck_policy_index_jobs_budget"
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_policy_index_jobs_attempts"),
        sa.CheckConstraint(
            "indexed_clause_count >= 0 AND skipped_clause_count >= 0",
            name="ck_policy_index_jobs_counts",
        ),
        sa.CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL AND "
            "lease_expires_at IS NOT NULL) OR status <> 'running'",
            name="ck_policy_index_jobs_running_lease",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["policy_embedding_profiles.id"],
            name="fk_policy_index_jobs_profile",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "policy_id", "policy_version_id"],
            [
                "governed_policy_versions.organization_id",
                "governed_policy_versions.policy_id",
                "governed_policy_versions.id",
            ],
            name="fk_policy_index_jobs_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_key", name="uq_policy_index_jobs_key"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_policy_index_jobs_org_public"
        ),
    )
    op.create_index(
        "ix_policy_index_jobs_claim",
        "policy_index_jobs",
        ["status", "available_at", "lease_expires_at"],
    )

    op.add_column(
        "governed_policy_clauses",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', coalesce(heading, '') || ' ' || "
                "coalesce(text, '') || ' ' || coalesce(applies_when, ''))",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_governed_policy_clauses_search_vector_gin",
        "governed_policy_clauses",
        ["search_vector"],
        postgresql_using="gin",
    )

    for name, type_ in (
        ("embedding_profile_key", sa.String(length=100)),
        ("retrieval_algorithm_version", sa.String(length=64)),
        ("query_fingerprint", sa.String(length=64)),
        ("dense_rank", sa.Integer()),
        ("lexical_rank", sa.Integer()),
        ("fused_retrieval_score", sa.Float()),
        ("retrieval_run_correlation_id", sa.String(length=100)),
    ):
        op.add_column("case_policy_evidence", sa.Column(name, type_, nullable=True))
    op.create_check_constraint(
        "ck_case_policy_evidence_fused_score",
        "case_policy_evidence",
        "fused_retrieval_score IS NULL OR fused_retrieval_score >= 0",
    )

    profile = sa.table(
        "policy_embedding_profiles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("profile_key", sa.String()),
        sa.column("environment", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("model", sa.String()),
        sa.column("dimensions", sa.Integer()),
        sa.column("normalization_version", sa.String()),
        sa.column("chunking_version", sa.String()),
        sa.column("index_version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("expected_clause_count", sa.Integer()),
        sa.column("indexed_clause_count", sa.Integer()),
        sa.column("build_fingerprint", sa.String()),
    )
    op.bulk_insert(
        profile,
        [
            {
                "id": DETERMINISTIC_PROFILE_ID,
                "profile_key": "deterministic-hash-v2-d512",
                "environment": "development",
                "provider": "deterministic",
                "model": "sha256-token-sign-v2",
                "dimensions": 512,
                "normalization_version": "policy-normalization-v2",
                "chunking_version": "governed-heading-v1",
                "index_version": "policy-hybrid-rrf-v2",
                "status": "building",
                "expected_clause_count": 0,
                "indexed_clause_count": 0,
                "build_fingerprint": (
                    "d3201950c8628cd7e037f93e4dedcadad0386a951a805b4f31e7831bd2487e84"
                ),
            },
            {
                "id": OPENAI_PROFILE_ID,
                "profile_key": "openai-text-embedding-3-small-v2-d512",
                "environment": "development",
                "provider": "openai",
                "model": "text-embedding-3-small",
                "dimensions": 512,
                "normalization_version": "policy-normalization-v2",
                "chunking_version": "governed-heading-v1",
                "index_version": "policy-hybrid-rrf-v2",
                "status": "building",
                "expected_clause_count": 0,
                "indexed_clause_count": 0,
                "build_fingerprint": (
                    "e1a6b6f0bb4b4604f35ceba2fa3515936defb85294de7c02bfec4890a2580ba2"
                ),
            },
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_case_policy_evidence_fused_score",
        "case_policy_evidence",
        type_="check",
    )
    for name in (
        "retrieval_run_correlation_id",
        "fused_retrieval_score",
        "lexical_rank",
        "dense_rank",
        "query_fingerprint",
        "retrieval_algorithm_version",
        "embedding_profile_key",
    ):
        op.drop_column("case_policy_evidence", name)
    op.drop_index(
        "ix_governed_policy_clauses_search_vector_gin",
        table_name="governed_policy_clauses",
    )
    op.drop_column("governed_policy_clauses", "search_vector")
    op.drop_index("ix_policy_index_jobs_claim", table_name="policy_index_jobs")
    op.drop_table("policy_index_jobs")
    op.drop_index(
        "ix_policy_clause_embeddings_v2_tenant_profile",
        table_name="governed_policy_clause_embeddings_v2",
    )
    op.drop_index(
        "ix_policy_clause_embeddings_v2_hnsw",
        table_name="governed_policy_clause_embeddings_v2",
    )
    op.drop_table("governed_policy_clause_embeddings_v2")
    op.drop_index(
        "uq_policy_embedding_profiles_active_environment",
        table_name="policy_embedding_profiles",
    )
    op.drop_table("policy_embedding_profiles")
