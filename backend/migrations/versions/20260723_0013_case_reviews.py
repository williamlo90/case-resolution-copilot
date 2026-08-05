"""Add tenant-scoped case reviews and immutable authorization snapshots.

Revision ID: 20260723_0013
Revises: 20260722_0012
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0013"
down_revision: str | None = "20260722_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=False),
        sa.Column("policy_state", sa.String(length=32), nullable=False),
        sa.Column("uncertainty", sa.String(length=16), nullable=False),
        sa.Column("impact_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("impact_currency", sa.String(length=3), nullable=True),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_by_public_id", sa.String(length=64), nullable=False),
        sa.Column("submitted_by_name", sa.String(length=200), nullable=False),
        sa.Column("submitted_by_role", sa.String(length=32), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("version > 0", name="ck_case_reviews_version"),
        sa.CheckConstraint(
            "status IN ('pending', 'reserved', 'approved', 'changes_requested', "
            "'rejected', 'escalated')",
            name="ck_case_reviews_status",
        ),
        sa.CheckConstraint(
            "policy_state IN ('supported', 'possible_conflict', 'missing')",
            name="ck_case_reviews_policy_state",
        ),
        sa.CheckConstraint(
            "uncertainty IN ('low', 'medium', 'high')",
            name="ck_case_reviews_uncertainty",
        ),
        sa.CheckConstraint(
            "submitted_by_role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_case_reviews_submitter_role",
        ),
        sa.CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_case_reviews_impact_pair",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_reviews_org_case",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id"],
            [
                "case_proposals.organization_id",
                "case_proposals.case_id",
                "case_proposals.id",
            ],
            name="fk_case_reviews_org_proposal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id", "proposal_version_id"],
            [
                "case_proposal_versions.organization_id",
                "case_proposal_versions.case_id",
                "case_proposal_versions.proposal_id",
                "case_proposal_versions.id",
            ],
            name="fk_case_reviews_org_proposal_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "submitted_by_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_reviews_org_submitter",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "public_id", name="uq_case_reviews_org_public"),
        sa.UniqueConstraint("organization_id", "case_id", "id", name="uq_case_reviews_org_case_id"),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_version_id",
            name="uq_case_reviews_org_proposal_version",
        ),
    )
    op.create_index(
        "ix_case_reviews_org_status_submitted",
        "case_reviews",
        ["organization_id", "status", "submitted_at"],
    )

    op.create_table(
        "case_review_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False),
        sa.Column("proposal_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("context_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("risk_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("risk_rule_version", sa.String(length=100), nullable=False),
        sa.Column("snapshot_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("approval_rule_id", sa.String(length=64), nullable=False),
        sa.Column("approval_rule_name", sa.String(length=300), nullable=False),
        sa.Column("approval_rule_explanation", sa.Text(), nullable=False),
        sa.Column("required_role", sa.String(length=32), nullable=False),
        sa.Column("approval_rule_version", sa.Integer(), nullable=False),
        sa.Column("execution_eligible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("case_version > 0", name="ck_case_review_snapshots_case_version"),
        sa.CheckConstraint(
            "proposal_version > 0", name="ck_case_review_snapshots_proposal_version"
        ),
        sa.CheckConstraint(
            "approval_rule_version > 0",
            name="ck_case_review_snapshots_rule_version",
        ),
        sa.CheckConstraint(
            "required_role IN ('supervisor', 'administrator')",
            name="ck_case_review_snapshots_required_role",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_case_review_snapshots_org_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id", "proposal_version_id"],
            [
                "case_proposal_versions.organization_id",
                "case_proposal_versions.case_id",
                "case_proposal_versions.proposal_id",
                "case_proposal_versions.id",
            ],
            name="fk_case_review_snapshots_org_proposal_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_review_snapshots_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            name="uq_case_review_snapshots_org_review",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            "id",
            name="uq_case_review_snapshots_org_review_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "snapshot_fingerprint",
            name="uq_case_review_snapshots_org_fingerprint",
        ),
    )

    op.create_table(
        "case_review_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("legacy_reservation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_public_id", sa.String(length=64), nullable=False),
        sa.Column("reviewer_name", sa.String(length=200), nullable=False),
        sa.Column("reviewer_role", sa.String(length=32), nullable=False),
        sa.Column("snapshot_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'consumed', 'expired')",
            name="ck_case_review_reservations_status",
        ),
        sa.CheckConstraint(
            "reviewer_role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_case_review_reservations_reviewer_role",
        ),
        sa.CheckConstraint(
            "(legacy_reservation_id IS NULL AND reviewer_id IS NOT NULL) OR "
            "(legacy_reservation_id IS NOT NULL AND reviewer_id IS NULL)",
            name="ck_case_review_reservations_lineage_actor",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_case_review_reservations_org_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id", "snapshot_id"],
            [
                "case_review_snapshots.organization_id",
                "case_review_snapshots.case_id",
                "case_review_snapshots.review_id",
                "case_review_snapshots.id",
            ],
            name="fk_case_review_reservations_org_snapshot",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "reviewer_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_review_reservations_org_reviewer",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_reservation_id"],
            ["reviewer_reservations.id"],
            name="fk_case_review_reservations_legacy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_review_reservations_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            "id",
            name="uq_case_review_reservations_org_review_id",
        ),
        sa.UniqueConstraint(
            "legacy_reservation_id",
            name="uq_case_review_reservations_legacy",
        ),
    )
    op.create_index(
        "uq_case_review_reservations_active",
        "case_review_reservations",
        ["organization_id", "review_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "case_review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("legacy_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_public_id", sa.String(length=64), nullable=False),
        sa.Column("reviewer_name", sa.String(length=200), nullable=False),
        sa.Column("reviewer_role", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("snapshot_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN ('approve', 'request_changes', 'reject', 'escalate')",
            name="ck_case_review_decisions_decision",
        ),
        sa.CheckConstraint(
            "reviewer_role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_case_review_decisions_reviewer_role",
        ),
        sa.CheckConstraint(
            "(legacy_decision_id IS NULL AND reviewer_id IS NOT NULL) OR "
            "(legacy_decision_id IS NOT NULL AND reviewer_id IS NULL)",
            name="ck_case_review_decisions_lineage_actor",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_case_review_decisions_org_review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id", "reservation_id"],
            [
                "case_review_reservations.organization_id",
                "case_review_reservations.case_id",
                "case_review_reservations.review_id",
                "case_review_reservations.id",
            ],
            name="fk_case_review_decisions_org_reservation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "reviewer_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_review_decisions_org_reviewer",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_decision_id"],
            ["approval_decisions.id"],
            name="fk_case_review_decisions_legacy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "public_id", name="uq_case_review_decisions_org_public"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            name="uq_case_review_decisions_org_review",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            "reservation_id",
            name="uq_case_review_decisions_org_reservation",
        ),
        sa.UniqueConstraint("legacy_decision_id", name="uq_case_review_decisions_legacy"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    review_count = connection.scalar(sa.text("SELECT count(*) FROM case_reviews"))
    if review_count:
        raise RuntimeError("Refusing to drop populated B5 case review data.")

    op.drop_table("case_review_decisions")
    op.drop_index(
        "uq_case_review_reservations_active",
        table_name="case_review_reservations",
    )
    op.drop_table("case_review_reservations")
    op.drop_table("case_review_snapshots")
    op.drop_index("ix_case_reviews_org_status_submitted", table_name="case_reviews")
    op.drop_table("case_reviews")
