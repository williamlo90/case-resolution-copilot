from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class ConnectionModel(Base):
    __tablename__ = "connections"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_connections_version"),
        CheckConstraint(
            "environment IN ('demo', 'sandbox', 'production')",
            name="ck_connections_environment",
        ),
        CheckConstraint(
            "health IN ('healthy', 'degraded', 'unavailable', 'not_configured')",
            name="ck_connections_health",
        ),
        CheckConstraint(
            "credential_status IN ('demo', 'connected', 'missing', 'expired')",
            name="ck_connections_credential_status",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_connections_org_public"),
        UniqueConstraint("organization_id", "id", name="uq_connections_org_id"),
        UniqueConstraint("organization_id", "name", name="uq_connections_org_name"),
        Index("ix_connections_org_health", "organization_id", "health"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(100), nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    health: Mapped[str] = mapped_column(String(24), nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_status: Mapped[str] = mapped_column(String(16), nullable=False)
    read_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    write_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    action_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    affected_work: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    runtime_config_fingerprint: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ConnectionHealthCheckModel(Base):
    __tablename__ = "connection_health_checks"
    __table_args__ = (
        CheckConstraint(
            "health IN ('healthy', 'degraded', 'unavailable', 'not_configured')",
            name="ck_connection_health_checks_health",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_connection_health_checks_org_public",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_connection_health_checks_org_connection",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "checked_by_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_connection_health_checks_org_actor",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_connection_health_checks_org_connection_checked",
            "organization_id",
            "connection_id",
            "checked_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    health: Mapped[str] = mapped_column(String(24), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    checked_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    checked_by_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    checked_by_name: Mapped[str] = mapped_column(String(200), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CaseActionModel(Base):
    __tablename__ = "case_actions"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="ck_case_actions_attempt_count"),
        CheckConstraint("version > 0", name="ck_case_actions_version"),
        CheckConstraint(
            "status IN ('ready', 'running', 'completed', 'failed_safe', "
            "'outcome_unknown', 'recovery_required')",
            name="ck_case_actions_status",
        ),
        CheckConstraint(
            "execution_blocker IS NULL OR execution_blocker IN "
            "('permission', 'duplicate', 'expired_approval', "
            "'connection_unavailable', 'stale_proposal')",
            name="ck_case_actions_blocker",
        ),
        CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_case_actions_impact_pair",
        ),
        CheckConstraint(
            "(owner_id IS NULL AND owner_public_id IS NULL AND owner_name IS NULL) OR "
            "(owner_id IS NOT NULL AND owner_public_id IS NOT NULL AND owner_name IS NOT NULL)",
            name="ck_case_actions_owner_snapshot",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_case_actions_org_public"),
        UniqueConstraint("organization_id", "case_id", "id", name="uq_case_actions_org_case_id"),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "proposed_action_id",
            name="uq_case_actions_org_proposed_action",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_case_actions_org_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_actions_org_case",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "case_id",
                "proposal_id",
                "proposal_version_id",
            ],
            [
                "case_proposal_versions.organization_id",
                "case_proposal_versions.case_id",
                "case_proposal_versions.proposal_id",
                "case_proposal_versions.id",
            ],
            name="fk_case_actions_org_proposal_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_case_actions_org_review",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["connections.organization_id", "connections.id"],
            name="fk_case_actions_org_connection",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "owner_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_actions_org_owner",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_case_actions_org_status_updated",
            "organization_id",
            "status",
            "updated_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposed_action_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_decision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    legacy_proposal_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("proposal_versions.id", ondelete="RESTRICT"),
    )
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    target: Mapped[str] = mapped_column(String(200), nullable=False)
    typed_parameters: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    impact_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    impact_currency: Mapped[str | None] = mapped_column(String(3))
    expected_outcome: Mapped[str] = mapped_column(String(1000), nullable=False)
    observed_outcome: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_blocker: Mapped[str | None] = mapped_column(String(32))
    execution_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    owner_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    owner_public_id: Mapped[str | None] = mapped_column(String(64))
    owner_name: Mapped[str | None] = mapped_column(String(200))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class CaseActionAttemptModel(Base):
    __tablename__ = "case_action_attempts"
    __table_args__ = (
        CheckConstraint("number > 0", name="ck_case_action_attempts_number"),
        CheckConstraint(
            "command IN ('execute', 'retry_safe', 'legacy_import')",
            name="ck_case_action_attempts_command",
        ),
        CheckConstraint(
            "outcome IN ('running', 'succeeded', 'failed_before_change', 'unknown')",
            name="ck_case_action_attempts_outcome",
        ),
        CheckConstraint(
            "side_effect_state IN ('not_attempted', 'none', 'confirmed', 'possible')",
            name="ck_case_action_attempts_side_effect",
        ),
        CheckConstraint(
            "actor_role IS NULL OR actor_role IN "
            "('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_case_action_attempts_actor_role",
        ),
        CheckConstraint(
            "(legacy_tool_attempt_id IS NULL AND actor_id IS NOT NULL "
            "AND actor_role IS NOT NULL) OR "
            "(legacy_tool_attempt_id IS NOT NULL AND actor_id IS NULL "
            "AND actor_role IS NULL)",
            name="ck_case_action_attempts_lineage_actor",
        ),
        CheckConstraint(
            "(outcome = 'running' AND finished_at IS NULL) OR "
            "(outcome <> 'running' AND finished_at IS NOT NULL)",
            name="ck_case_action_attempts_finished",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_action_attempts_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "action_id",
            "number",
            name="uq_case_action_attempts_org_action_number",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "action_id",
            "id",
            name="uq_case_action_attempts_org_action_id",
        ),
        UniqueConstraint(
            "legacy_tool_attempt_id",
            name="uq_case_action_attempts_legacy",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "action_id"],
            ["case_actions.organization_id", "case_actions.case_id", "case_actions.id"],
            name="fk_case_action_attempts_org_action",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_action_attempts_org_actor",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_case_action_attempts_org_action_started",
            "organization_id",
            "action_id",
            "started_at",
        ),
        Index(
            "uq_case_action_attempts_running",
            "organization_id",
            "action_id",
            unique=True,
            postgresql_where=text("outcome = 'running'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    actor_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(32))
    legacy_tool_attempt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tool_attempts.id", ondelete="RESTRICT"),
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    command: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    side_effect_state: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_fingerprint: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseActionReceiptModel(Base):
    __tablename__ = "case_action_receipts"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_action_receipts_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "action_id",
            name="uq_case_action_receipts_org_action",
        ),
        UniqueConstraint(
            "organization_id",
            "provider",
            "idempotency_key",
            name="uq_case_action_receipts_org_provider_idempotency",
        ),
        UniqueConstraint(
            "legacy_external_receipt_id",
            name="uq_case_action_receipts_legacy",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "action_id"],
            ["case_actions.organization_id", "case_actions.case_id", "case_actions.id"],
            name="fk_case_action_receipts_org_action",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    legacy_external_receipt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("external_receipts.id", ondelete="RESTRICT"),
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    external_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    data_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CaseActionReconciliationModel(Base):
    __tablename__ = "case_action_reconciliations"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('running', 'confirmed_completed', 'confirmed_absent', 'still_unknown')",
            name="ck_case_action_reconciliations_outcome",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_action_reconciliations_org_public",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "action_id"],
            ["case_actions.organization_id", "case_actions.case_id", "case_actions.id"],
            name="fk_case_action_reconciliations_org_action",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_action_reconciliations_org_actor",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_case_action_reconciliations_org_action_checked",
            "organization_id",
            "action_id",
            "checked_at",
        ),
        Index(
            "uq_case_action_reconciliations_running",
            "organization_id",
            "action_id",
            unique=True,
            postgresql_where=text("outcome = 'running'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(200))
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
