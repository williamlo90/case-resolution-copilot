"""Add tenant-scoped decision briefs and immutable proposal snapshots.

Revision ID: 20260722_0012
Revises: 20260722_0011
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260722_0012"
down_revision: str | None = "20260722_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_business_snapshots_org_case_id",
        "business_object_snapshots",
        ["organization_id", "case_id", "id"],
    )
    op.create_unique_constraint(
        "uq_case_policy_evidence_org_id",
        "case_policy_evidence",
        ["organization_id", "id"],
    )
    op.create_unique_constraint(
        "uq_case_policy_evidence_org_case_id",
        "case_policy_evidence",
        ["organization_id", "case_id", "id"],
    )

    op.create_table(
        "case_analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("policy_status", sa.String(length=16), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("initiated_by", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("graph_version", sa.String(length=100), nullable=False),
        sa.Column("risk_rule_version", sa.String(length=100), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("case_version > 0", name="ck_case_analysis_runs_case_version"),
        sa.CheckConstraint(
            "status IN ('completed', 'abstained')", name="ck_case_analysis_runs_status"
        ),
        sa.CheckConstraint(
            "policy_status IN ('relevant', 'missing', 'inapplicable', 'stale', 'conflicting')",
            name="ck_case_analysis_runs_policy_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_analysis_runs_org_case",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_case_analysis_runs_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id", "case_id", "id", name="uq_case_analysis_runs_org_case_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "input_fingerprint",
            name="uq_case_analysis_runs_org_case_input",
        ),
    )
    op.create_index(
        "ix_case_analysis_runs_org_case_completed",
        "case_analysis_runs",
        ["organization_id", "case_id", "completed_at"],
    )

    op.create_table(
        "case_analysis_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("output_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("sequence > 0", name="ck_case_analysis_checkpoints_sequence"),
        sa.CheckConstraint(
            "status IN ('completed', 'abstained')",
            name="ck_case_analysis_checkpoints_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "analysis_run_id"],
            [
                "case_analysis_runs.organization_id",
                "case_analysis_runs.case_id",
                "case_analysis_runs.id",
            ],
            name="fk_case_analysis_checkpoints_org_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_analysis_checkpoints_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "analysis_run_id",
            "sequence",
            name="uq_case_analysis_checkpoints_org_run_sequence",
        ),
    )

    op.create_table(
        "case_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("current_version > 0", name="ck_case_proposals_current_version"),
        sa.CheckConstraint("version > 0", name="ck_case_proposals_version"),
        sa.CheckConstraint(
            "state IN ('draft', 'information_needed', 'ready_for_review', 'under_review', "
            "'approved', 'rejected')",
            name="ck_case_proposals_state",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_proposals_org_case",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_case_proposals_org_id"),
        sa.UniqueConstraint(
            "organization_id", "case_id", "id", name="uq_case_proposals_org_case_id"
        ),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_case_proposals_org_public"),
        sa.UniqueConstraint("organization_id", "case_id", name="uq_case_proposals_org_case"),
    )

    op.create_table(
        "case_proposal_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legacy_proposal_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("outcome", sa.String(length=500), nullable=False),
        sa.Column("impact_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("impact_currency", sa.String(length=3), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("uncertainty", sa.String(length=1000), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("facts", postgresql.JSONB(), nullable=False),
        sa.Column("missing_information", postgresql.JSONB(), nullable=False),
        sa.Column("risks", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("risk_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("risk_rule_version", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("graph_version", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_case_proposal_versions_version"),
        sa.CheckConstraint(
            "state IN ('draft', 'information_needed', 'ready_for_review', 'under_review', "
            "'approved', 'rejected')",
            name="ck_case_proposal_versions_state",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="ck_case_proposal_versions_confidence",
        ),
        sa.CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_case_proposal_versions_impact_pair",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id"],
            [
                "case_proposals.organization_id",
                "case_proposals.case_id",
                "case_proposals.id",
            ],
            name="fk_case_proposal_versions_org_proposal",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "analysis_run_id"],
            [
                "case_analysis_runs.organization_id",
                "case_analysis_runs.case_id",
                "case_analysis_runs.id",
            ],
            name="fk_case_proposal_versions_org_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_proposal_version_id"],
            ["proposal_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_case_proposal_versions_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_id",
            "version",
            name="uq_case_proposal_versions_org_proposal_version",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_id",
            "id",
            name="uq_case_proposal_versions_org_proposal_id",
        ),
        sa.UniqueConstraint("analysis_run_id", name="uq_case_proposal_versions_analysis_run"),
        sa.UniqueConstraint("legacy_proposal_version_id", name="uq_case_proposal_versions_legacy"),
    )
    op.create_index(
        "ix_case_proposal_versions_org_case_created",
        "case_proposal_versions",
        ["organization_id", "case_id", "created_at"],
    )

    op.create_table(
        "proposal_evidence_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id", "proposal_version_id"],
            [
                "case_proposal_versions.organization_id",
                "case_proposal_versions.case_id",
                "case_proposal_versions.proposal_id",
                "case_proposal_versions.id",
            ],
            name="fk_proposal_evidence_bindings_org_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "evidence_id"],
            [
                "case_policy_evidence.organization_id",
                "case_policy_evidence.case_id",
                "case_policy_evidence.id",
            ],
            name="fk_proposal_evidence_bindings_org_evidence",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_version_id",
            "evidence_id",
            name="uq_proposal_evidence_bindings_version_evidence",
        ),
    )

    op.create_table(
        "proposal_context_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("context_fingerprint", sa.String(length=64), nullable=False),
        sa.CheckConstraint("snapshot_version > 0", name="ck_proposal_context_snapshot_version"),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id", "proposal_version_id"],
            [
                "case_proposal_versions.organization_id",
                "case_proposal_versions.case_id",
                "case_proposal_versions.proposal_id",
                "case_proposal_versions.id",
            ],
            name="fk_proposal_context_bindings_org_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "context_id"],
            [
                "business_object_snapshots.organization_id",
                "business_object_snapshots.case_id",
                "business_object_snapshots.id",
            ],
            name="fk_proposal_context_bindings_org_context",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_version_id",
            "context_id",
            name="uq_proposal_context_bindings_version_context",
        ),
    )

    op.create_table(
        "case_proposed_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("parameters", postgresql.JSONB(), nullable=False),
        sa.Column("impact_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("impact_currency", sa.String(length=3), nullable=True),
        sa.Column("expected_outcome", sa.String(length=1000), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_case_proposed_actions_impact_pair",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id", "proposal_version_id"],
            [
                "case_proposal_versions.organization_id",
                "case_proposal_versions.case_id",
                "case_proposal_versions.proposal_id",
                "case_proposal_versions.id",
            ],
            name="fk_case_proposed_actions_org_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_case_proposed_actions_org_public"
        ),
    )

    op.create_table(
        "proposal_response_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_proposal_response_drafts_version"),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'blocked')",
            name="ck_proposal_response_drafts_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id", "proposal_version_id"],
            [
                "case_proposal_versions.organization_id",
                "case_proposal_versions.case_id",
                "case_proposal_versions.proposal_id",
                "case_proposal_versions.id",
            ],
            name="fk_proposal_response_drafts_org_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_proposal_response_drafts_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_version_id",
            name="uq_proposal_response_drafts_org_version",
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    proposal_count = connection.scalar(sa.text("SELECT count(*) FROM case_proposals"))
    run_count = connection.scalar(sa.text("SELECT count(*) FROM case_analysis_runs"))
    if proposal_count or run_count:
        raise RuntimeError("Refusing to drop populated B4 decision brief data.")

    op.drop_table("proposal_response_drafts")
    op.drop_table("case_proposed_actions")
    op.drop_table("proposal_context_bindings")
    op.drop_table("proposal_evidence_bindings")
    op.drop_index("ix_case_proposal_versions_org_case_created", table_name="case_proposal_versions")
    op.drop_table("case_proposal_versions")
    op.drop_table("case_proposals")
    op.drop_table("case_analysis_checkpoints")
    op.drop_index("ix_case_analysis_runs_org_case_completed", table_name="case_analysis_runs")
    op.drop_table("case_analysis_runs")
    op.drop_constraint(
        "uq_case_policy_evidence_org_case_id", "case_policy_evidence", type_="unique"
    )
    op.drop_constraint("uq_case_policy_evidence_org_id", "case_policy_evidence", type_="unique")
    op.drop_constraint(
        "uq_business_snapshots_org_case_id", "business_object_snapshots", type_="unique"
    )
