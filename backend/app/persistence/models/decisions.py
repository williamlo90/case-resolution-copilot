from datetime import datetime
from decimal import Decimal
from typing import Any
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class CaseAnalysisGenerationModel(Base):
    __tablename__ = "case_analysis_generations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_case_analysis_generations_status",
        ),
        CheckConstraint(
            "fence_token > 0",
            name="ck_case_analysis_generations_fence_token",
        ),
        CheckConstraint(
            "attempt_count > 0",
            name="ck_case_analysis_generations_attempt_count",
        ),
        CheckConstraint(
            "(status = 'completed' AND analysis_run_id IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND analysis_run_id IS NULL "
            "AND completed_at IS NULL)",
            name="ck_case_analysis_generations_completion",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "input_fingerprint",
            name="uq_case_analysis_generations_org_case_input",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_analysis_generations_org_case",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "analysis_run_id"],
            [
                "case_analysis_runs.organization_id",
                "case_analysis_runs.case_id",
                "case_analysis_runs.id",
            ],
            name="fk_case_analysis_generations_org_run",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_case_analysis_generations_running_expiry",
            "status",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_token: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, default=uuid4
    )
    fence_token: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analysis_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseAnalysisRunModel(Base):
    __tablename__ = "case_analysis_runs"
    __table_args__ = (
        CheckConstraint("case_version > 0", name="ck_case_analysis_runs_case_version"),
        CheckConstraint(
            "status IN ('completed', 'abstained')", name="ck_case_analysis_runs_status"
        ),
        CheckConstraint(
            "policy_status IN ('relevant', 'missing', 'inapplicable', 'stale', 'conflicting')",
            name="ck_case_analysis_runs_policy_status",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_case_analysis_runs_org_public"),
        UniqueConstraint(
            "organization_id", "case_id", "id", name="uq_case_analysis_runs_org_case_id"
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "input_fingerprint",
            name="uq_case_analysis_runs_org_case_input",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_analysis_runs_org_case",
            ondelete="CASCADE",
        ),
        Index(
            "ix_case_analysis_runs_org_case_completed",
            "organization_id",
            "case_id",
            "completed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    policy_status: Mapped[str] = mapped_column(String(16), nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    initiated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    graph_version: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CaseAnalysisCheckpointModel(Base):
    __tablename__ = "case_analysis_checkpoints"
    __table_args__ = (
        CheckConstraint("sequence > 0", name="ck_case_analysis_checkpoints_sequence"),
        CheckConstraint(
            "status IN ('completed', 'abstained')",
            name="ck_case_analysis_checkpoints_status",
        ),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_case_analysis_checkpoints_org_public"
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "analysis_run_id",
            "sequence",
            name="uq_case_analysis_checkpoints_org_run_sequence",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "analysis_run_id"],
            [
                "case_analysis_runs.organization_id",
                "case_analysis_runs.case_id",
                "case_analysis_runs.id",
            ],
            name="fk_case_analysis_checkpoints_org_run",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    output_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CaseProposalModel(Base):
    __tablename__ = "case_proposals"
    __table_args__ = (
        CheckConstraint("current_version > 0", name="ck_case_proposals_current_version"),
        CheckConstraint("version > 0", name="ck_case_proposals_version"),
        CheckConstraint(
            "state IN ('draft', 'information_needed', 'ready_for_review', 'under_review', "
            "'approved', 'rejected')",
            name="ck_case_proposals_state",
        ),
        UniqueConstraint("organization_id", "id", name="uq_case_proposals_org_id"),
        UniqueConstraint("organization_id", "case_id", "id", name="uq_case_proposals_org_case_id"),
        UniqueConstraint("organization_id", "public_id", name="uq_case_proposals_org_public"),
        UniqueConstraint("organization_id", "case_id", name="uq_case_proposals_org_case"),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_proposals_org_case",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class CaseProposalVersionModel(Base):
    __tablename__ = "case_proposal_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_case_proposal_versions_version"),
        CheckConstraint(
            "state IN ('draft', 'information_needed', 'ready_for_review', 'under_review', "
            "'approved', 'rejected')",
            name="ck_case_proposal_versions_state",
        ),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="ck_case_proposal_versions_confidence",
        ),
        CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_case_proposal_versions_impact_pair",
        ),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_case_proposal_versions_org_public"
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_id",
            "version",
            name="uq_case_proposal_versions_org_proposal_version",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_id",
            "id",
            name="uq_case_proposal_versions_org_proposal_id",
        ),
        UniqueConstraint("analysis_run_id", name="uq_case_proposal_versions_analysis_run"),
        UniqueConstraint("legacy_proposal_version_id", name="uq_case_proposal_versions_legacy"),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id"],
            [
                "case_proposals.organization_id",
                "case_proposals.case_id",
                "case_proposals.id",
            ],
            name="fk_case_proposal_versions_org_proposal",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "analysis_run_id"],
            [
                "case_analysis_runs.organization_id",
                "case_analysis_runs.case_id",
                "case_analysis_runs.id",
            ],
            name="fk_case_proposal_versions_org_run",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_case_proposal_versions_org_case_created",
            "organization_id",
            "case_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    analysis_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    legacy_proposal_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("proposal_versions.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    outcome: Mapped[str] = mapped_column(String(500), nullable=False)
    impact_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    impact_currency: Mapped[str | None] = mapped_column(String(3))
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    uncertainty: Mapped[str] = mapped_column(String(1000), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    facts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    missing_information: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    risks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    graph_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ProposalEvidenceBindingModel(Base):
    __tablename__ = "proposal_evidence_bindings"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_version_id",
            "evidence_id",
            name="uq_proposal_evidence_bindings_version_evidence",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["organization_id", "case_id", "evidence_id"],
            [
                "case_policy_evidence.organization_id",
                "case_policy_evidence.case_id",
                "case_policy_evidence.id",
            ],
            name="fk_proposal_evidence_bindings_org_evidence",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    evidence_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class ProposalContextBindingModel(Base):
    __tablename__ = "proposal_context_bindings"
    __table_args__ = (
        CheckConstraint("snapshot_version > 0", name="ck_proposal_context_snapshot_version"),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_version_id",
            "context_id",
            name="uq_proposal_context_bindings_version_context",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["organization_id", "case_id", "context_id"],
            [
                "business_object_snapshots.organization_id",
                "business_object_snapshots.case_id",
                "business_object_snapshots.id",
            ],
            name="fk_proposal_context_bindings_org_context",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    context_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class CaseProposedActionModel(Base):
    __tablename__ = "case_proposed_actions"
    __table_args__ = (
        CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_case_proposed_actions_impact_pair",
        ),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_case_proposed_actions_org_public"
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_id",
            "proposal_version_id",
            "id",
            name="uq_case_proposed_actions_org_version_id",
        ),
        ForeignKeyConstraint(
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
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    parameters: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    impact_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    impact_currency: Mapped[str | None] = mapped_column(String(3))
    expected_outcome: Mapped[str] = mapped_column(String(1000), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ProposalResponseDraftModel(Base):
    __tablename__ = "proposal_response_drafts"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_proposal_response_drafts_version"),
        CheckConstraint(
            "status IN ('draft', 'ready', 'blocked')",
            name="ck_proposal_response_drafts_status",
        ),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_proposal_response_drafts_org_public"
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_version_id",
            name="uq_proposal_response_drafts_org_version",
        ),
        ForeignKeyConstraint(
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
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
