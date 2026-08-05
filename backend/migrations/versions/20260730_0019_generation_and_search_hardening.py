"""Add decision generation leases and bounded retrieval/search indexes.

Revision ID: 20260730_0019
Revises: 20260730_0018
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260730_0019"
down_revision: str | None = "20260730_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_analysis_generations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("owner_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fence_token", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_case_analysis_generations_status",
        ),
        sa.CheckConstraint(
            "fence_token > 0",
            name="ck_case_analysis_generations_fence_token",
        ),
        sa.CheckConstraint(
            "attempt_count > 0",
            name="ck_case_analysis_generations_attempt_count",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND analysis_run_id IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND analysis_run_id IS NULL "
            "AND completed_at IS NULL)",
            name="ck_case_analysis_generations_completion",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_analysis_generations_org_case",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "analysis_run_id"],
            [
                "case_analysis_runs.organization_id",
                "case_analysis_runs.case_id",
                "case_analysis_runs.id",
            ],
            name="fk_case_analysis_generations_org_run",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "input_fingerprint",
            name="uq_case_analysis_generations_org_case_input",
        ),
    )
    op.create_index(
        "ix_case_analysis_generations_running_expiry",
        "case_analysis_generations",
        ["status", "expires_at"],
    )

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    for column in (
        "case_categories",
        "products",
        "regions",
        "channels",
        "customer_tiers",
    ):
        op.create_index(
            f"ix_policy_versions_{column}_gin",
            "governed_policy_versions",
            [column],
            postgresql_using="gin",
            postgresql_ops={column: "jsonb_path_ops"},
        )
    op.create_index(
        "ix_policy_clauses_embedding_hnsw",
        "governed_policy_clauses",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )
    for table, column, name in (
        ("cases", "public_id", "ix_cases_public_id_trgm"),
        ("cases", "external_reference", "ix_cases_external_reference_trgm"),
        ("cases", "issue", "ix_cases_issue_trgm"),
        ("case_customers", "name", "ix_case_customers_name_trgm"),
    ):
        op.create_index(
            name,
            table,
            [column],
            postgresql_using="gin",
            postgresql_ops={column: "gin_trgm_ops"},
        )


def downgrade() -> None:
    for table, name in (
        ("case_customers", "ix_case_customers_name_trgm"),
        ("cases", "ix_cases_issue_trgm"),
        ("cases", "ix_cases_external_reference_trgm"),
        ("cases", "ix_cases_public_id_trgm"),
        ("governed_policy_clauses", "ix_policy_clauses_embedding_hnsw"),
    ):
        op.drop_index(name, table_name=table)
    for column in reversed(
        (
            "case_categories",
            "products",
            "regions",
            "channels",
            "customer_tiers",
        )
    ):
        op.drop_index(
            f"ix_policy_versions_{column}_gin",
            table_name="governed_policy_versions",
        )
    op.drop_index(
        "ix_case_analysis_generations_running_expiry",
        table_name="case_analysis_generations",
    )
    op.drop_table("case_analysis_generations")
