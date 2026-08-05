"""Add tenant-scoped controlled actions and connection health.

Revision ID: 20260723_0014
Revises: 20260723_0013
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0014"
down_revision: str | None = "20260723_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_case_proposed_actions_org_version_id",
        "case_proposed_actions",
        [
            "organization_id",
            "case_id",
            "proposal_id",
            "proposal_version_id",
            "id",
        ],
    )
    op.create_unique_constraint(
        "uq_case_review_decisions_org_review_id",
        "case_review_decisions",
        ["organization_id", "case_id", "review_id", "id"],
    )

    op.create_table(
        "connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider_type", sa.String(length=100), nullable=False),
        sa.Column("adapter_key", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column("health", sa.String(length=24), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_status", sa.String(length=16), nullable=False),
        sa.Column(
            "read_capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "write_capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "action_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "affected_work",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.CheckConstraint("version > 0", name="ck_connections_version"),
        sa.CheckConstraint(
            "environment IN ('demo', 'sandbox', 'production')",
            name="ck_connections_environment",
        ),
        sa.CheckConstraint(
            "health IN ('healthy', 'degraded', 'unavailable', 'not_configured')",
            name="ck_connections_health",
        ),
        sa.CheckConstraint(
            "credential_status IN ('demo', 'connected', 'missing', 'expired')",
            name="ck_connections_credential_status",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_connections_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_connections_org_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            name="uq_connections_org_name",
        ),
    )
    op.create_index(
        "ix_connections_org_health",
        "connections",
        ["organization_id", "health"],
    )

    op.create_table(
        "connection_health_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("health", sa.String(length=24), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("checked_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checked_by_public_id", sa.String(length=64), nullable=False),
        sa.Column("checked_by_name", sa.String(length=200), nullable=False),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "health IN ('healthy', 'degraded', 'unavailable', 'not_configured')",
            name="ck_connection_health_checks_health",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_connection_health_checks_org_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "checked_by_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_connection_health_checks_org_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_connection_health_checks_org_public",
        ),
    )
    op.create_index(
        "ix_connection_health_checks_org_connection_checked",
        "connection_health_checks",
        ["organization_id", "connection_id", "checked_at"],
    )

    op.create_table(
        "case_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposed_action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_decision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "legacy_proposal_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=False),
        sa.Column(
            "typed_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("impact_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("impact_currency", sa.String(length=3), nullable=True),
        sa.Column("expected_outcome", sa.String(length=1000), nullable=False),
        sa.Column("observed_outcome", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("execution_blocker", sa.String(length=32), nullable=True),
        sa.Column(
            "execution_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "authorization_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_public_id", sa.String(length=64), nullable=True),
        sa.Column("owner_name", sa.String(length=200), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_case_actions_attempt_count",
        ),
        sa.CheckConstraint("version > 0", name="ck_case_actions_version"),
        sa.CheckConstraint(
            "status IN ('ready', 'running', 'completed', 'failed_safe', "
            "'outcome_unknown', 'recovery_required')",
            name="ck_case_actions_status",
        ),
        sa.CheckConstraint(
            "execution_blocker IS NULL OR execution_blocker IN "
            "('permission', 'duplicate', 'expired_approval', "
            "'connection_unavailable', 'stale_proposal')",
            name="ck_case_actions_blocker",
        ),
        sa.CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_case_actions_impact_pair",
        ),
        sa.CheckConstraint(
            "(owner_id IS NULL AND owner_public_id IS NULL AND owner_name IS NULL) OR "
            "(owner_id IS NOT NULL AND owner_public_id IS NOT NULL "
            "AND owner_name IS NOT NULL)",
            name="ck_case_actions_owner_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_actions_org_case",
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
            name="fk_case_actions_org_proposal_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "case_id",
                "proposal_id",
                "proposal_version_id",
                "proposed_action_id",
            ],
            [
                "case_proposed_actions.organization_id",
                "case_proposed_actions.case_id",
                "case_proposed_actions.proposal_id",
                "case_proposed_actions.proposal_version_id",
                "case_proposed_actions.id",
            ],
            name="fk_case_actions_org_proposed_action",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_case_actions_org_review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id", "review_snapshot_id"],
            [
                "case_review_snapshots.organization_id",
                "case_review_snapshots.case_id",
                "case_review_snapshots.review_id",
                "case_review_snapshots.id",
            ],
            name="fk_case_actions_org_review_snapshot",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id", "review_decision_id"],
            [
                "case_review_decisions.organization_id",
                "case_review_decisions.case_id",
                "case_review_decisions.review_id",
                "case_review_decisions.id",
            ],
            name="fk_case_actions_org_review_decision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_case_actions_org_connection",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_actions_org_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_proposal_version_id"],
            ["proposal_versions.id"],
            name="fk_case_actions_legacy_proposal_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_actions_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "id",
            name="uq_case_actions_org_case_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "proposed_action_id",
            name="uq_case_actions_org_proposed_action",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_case_actions_org_idempotency",
        ),
    )
    op.create_index(
        "ix_case_actions_org_status_updated",
        "case_actions",
        ["organization_id", "status", "updated_at"],
    )

    op.create_table(
        "case_action_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_public_id", sa.String(length=64), nullable=False),
        sa.Column("actor_name", sa.String(length=200), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column(
            "legacy_tool_attempt_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("command", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("side_effect_state", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "number > 0",
            name="ck_case_action_attempts_number",
        ),
        sa.CheckConstraint(
            "command IN ('execute', 'retry_safe', 'legacy_import')",
            name="ck_case_action_attempts_command",
        ),
        sa.CheckConstraint(
            "outcome IN ('running', 'succeeded', 'failed_before_change', 'unknown')",
            name="ck_case_action_attempts_outcome",
        ),
        sa.CheckConstraint(
            "side_effect_state IN ('not_attempted', 'none', 'confirmed', 'possible')",
            name="ck_case_action_attempts_side_effect",
        ),
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role IN "
            "('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_case_action_attempts_actor_role",
        ),
        sa.CheckConstraint(
            "(legacy_tool_attempt_id IS NULL AND actor_id IS NOT NULL "
            "AND actor_role IS NOT NULL) OR "
            "(legacy_tool_attempt_id IS NOT NULL AND actor_id IS NULL "
            "AND actor_role IS NULL)",
            name="ck_case_action_attempts_lineage_actor",
        ),
        sa.CheckConstraint(
            "(outcome = 'running' AND finished_at IS NULL) OR "
            "(outcome <> 'running' AND finished_at IS NOT NULL)",
            name="ck_case_action_attempts_finished",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "action_id"],
            ["case_actions.organization_id", "case_actions.case_id", "case_actions.id"],
            name="fk_case_action_attempts_org_action",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_action_attempts_org_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_tool_attempt_id"],
            ["tool_attempts.id"],
            name="fk_case_action_attempts_legacy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_action_attempts_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "action_id",
            "number",
            name="uq_case_action_attempts_org_action_number",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "action_id",
            "id",
            name="uq_case_action_attempts_org_action_id",
        ),
        sa.UniqueConstraint(
            "legacy_tool_attempt_id",
            name="uq_case_action_attempts_legacy",
        ),
    )
    op.create_index(
        "ix_case_action_attempts_org_action_started",
        "case_action_attempts",
        ["organization_id", "action_id", "started_at"],
    )
    op.create_index(
        "uq_case_action_attempts_running",
        "case_action_attempts",
        ["organization_id", "action_id"],
        unique=True,
        postgresql_where=sa.text("outcome = 'running'"),
    )

    op.create_table(
        "case_action_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "legacy_external_receipt_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("external_reference", sa.String(length=200), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("data_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "action_id"],
            ["case_actions.organization_id", "case_actions.case_id", "case_actions.id"],
            name="fk_case_action_receipts_org_action",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "action_id", "attempt_id"],
            [
                "case_action_attempts.organization_id",
                "case_action_attempts.case_id",
                "case_action_attempts.action_id",
                "case_action_attempts.id",
            ],
            name="fk_case_action_receipts_org_attempt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_external_receipt_id"],
            ["external_receipts.id"],
            name="fk_case_action_receipts_legacy",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_action_receipts_org_public",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "case_id",
            "action_id",
            name="uq_case_action_receipts_org_action",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "idempotency_key",
            name="uq_case_action_receipts_org_provider_idempotency",
        ),
        sa.UniqueConstraint(
            "legacy_external_receipt_id",
            name="uq_case_action_receipts_legacy",
        ),
    )

    op.create_table(
        "case_action_reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_public_id", sa.String(length=64), nullable=False),
        sa.Column("actor_name", sa.String(length=200), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("external_reference", sa.String(length=200), nullable=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "outcome IN ('running', 'confirmed_completed', 'confirmed_absent', 'still_unknown')",
            name="ck_case_action_reconciliations_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "action_id"],
            ["case_actions.organization_id", "case_actions.case_id", "case_actions.id"],
            name="fk_case_action_reconciliations_org_action",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_action_reconciliations_org_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_action_reconciliations_org_public",
        ),
    )
    op.create_index(
        "ix_case_action_reconciliations_org_action_checked",
        "case_action_reconciliations",
        ["organization_id", "action_id", "checked_at"],
    )
    op.create_index(
        "uq_case_action_reconciliations_running",
        "case_action_reconciliations",
        ["organization_id", "action_id"],
        unique=True,
        postgresql_where=sa.text("outcome = 'running'"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    populated = connection.scalar(
        sa.text(
            """
            SELECT
                (SELECT count(*) FROM connections)
              + (SELECT count(*) FROM connection_health_checks)
              + (SELECT count(*) FROM case_actions)
              + (SELECT count(*) FROM case_action_attempts)
              + (SELECT count(*) FROM case_action_receipts)
              + (SELECT count(*) FROM case_action_reconciliations)
            """
        )
    )
    if populated:
        raise RuntimeError("Refusing to drop populated B6 action or connection data.")

    op.drop_index(
        "uq_case_action_reconciliations_running",
        table_name="case_action_reconciliations",
    )
    op.drop_index(
        "ix_case_action_reconciliations_org_action_checked",
        table_name="case_action_reconciliations",
    )
    op.drop_table("case_action_reconciliations")
    op.drop_table("case_action_receipts")
    op.drop_index(
        "uq_case_action_attempts_running",
        table_name="case_action_attempts",
    )
    op.drop_index(
        "ix_case_action_attempts_org_action_started",
        table_name="case_action_attempts",
    )
    op.drop_table("case_action_attempts")
    op.drop_index(
        "ix_case_actions_org_status_updated",
        table_name="case_actions",
    )
    op.drop_table("case_actions")
    op.drop_index(
        "ix_connection_health_checks_org_connection_checked",
        table_name="connection_health_checks",
    )
    op.drop_table("connection_health_checks")
    op.drop_index("ix_connections_org_health", table_name="connections")
    op.drop_table("connections")

    op.drop_constraint(
        "uq_case_review_decisions_org_review_id",
        "case_review_decisions",
        type_="unique",
    )
    op.drop_constraint(
        "uq_case_proposed_actions_org_version_id",
        "case_proposed_actions",
        type_="unique",
    )
