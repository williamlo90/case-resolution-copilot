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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class CaseReviewModel(Base):
    __tablename__ = "case_reviews"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_case_reviews_version"),
        CheckConstraint(
            "status IN ('pending', 'reserved', 'approved', 'changes_requested', "
            "'rejected', 'escalated')",
            name="ck_case_reviews_status",
        ),
        CheckConstraint(
            "policy_state IN ('supported', 'possible_conflict', 'missing')",
            name="ck_case_reviews_policy_state",
        ),
        CheckConstraint(
            "uncertainty IN ('low', 'medium', 'high')",
            name="ck_case_reviews_uncertainty",
        ),
        CheckConstraint(
            "submitted_by_role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_case_reviews_submitter_role",
        ),
        CheckConstraint(
            "(impact_amount IS NULL AND impact_currency IS NULL) OR "
            "(impact_amount >= 0 AND char_length(impact_currency) = 3)",
            name="ck_case_reviews_impact_pair",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_case_reviews_org_public"),
        UniqueConstraint("organization_id", "case_id", "id", name="uq_case_reviews_org_case_id"),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "proposal_version_id",
            name="uq_case_reviews_org_proposal_version",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_reviews_org_case",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "proposal_id"],
            [
                "case_proposals.organization_id",
                "case_proposals.case_id",
                "case_proposals.id",
            ],
            name="fk_case_reviews_org_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["organization_id", "submitted_by_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_reviews_org_submitter",
            ondelete="RESTRICT",
        ),
        Index("ix_case_reviews_org_status_submitted", "organization_id", "status", "submitted_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_state: Mapped[str] = mapped_column(String(32), nullable=False)
    uncertainty: Mapped[str] = mapped_column(String(16), nullable=False)
    impact_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    impact_currency: Mapped[str | None] = mapped_column(String(3))
    submitted_by_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    submitted_by_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_by_name: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_by_role: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class CaseReviewSnapshotModel(Base):
    __tablename__ = "case_review_snapshots"
    __table_args__ = (
        CheckConstraint("case_version > 0", name="ck_case_review_snapshots_case_version"),
        CheckConstraint("proposal_version > 0", name="ck_case_review_snapshots_proposal_version"),
        CheckConstraint(
            "approval_rule_version > 0",
            name="ck_case_review_snapshots_rule_version",
        ),
        CheckConstraint(
            "required_role IN ('supervisor', 'administrator')",
            name="ck_case_review_snapshots_required_role",
        ),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_case_review_snapshots_org_public"
        ),
        UniqueConstraint(
            "organization_id", "case_id", "review_id", name="uq_case_review_snapshots_org_review"
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            "id",
            name="uq_case_review_snapshots_org_review_id",
        ),
        UniqueConstraint(
            "organization_id",
            "snapshot_fingerprint",
            name="uq_case_review_snapshots_org_fingerprint",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_case_review_snapshots_org_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
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
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    proposal_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposal_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_rule_name: Mapped[str] = mapped_column(String(300), nullable=False)
    approval_rule_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    required_role: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CaseReviewReservationModel(Base):
    __tablename__ = "case_review_reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'consumed', 'expired')",
            name="ck_case_review_reservations_status",
        ),
        CheckConstraint(
            "reviewer_role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_case_review_reservations_reviewer_role",
        ),
        CheckConstraint(
            "(legacy_reservation_id IS NULL AND reviewer_id IS NOT NULL) OR "
            "(legacy_reservation_id IS NOT NULL AND reviewer_id IS NULL)",
            name="ck_case_review_reservations_lineage_actor",
        ),
        UniqueConstraint(
            "organization_id",
            "public_id",
            name="uq_case_review_reservations_org_public",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            "id",
            name="uq_case_review_reservations_org_review_id",
        ),
        UniqueConstraint(
            "legacy_reservation_id",
            name="uq_case_review_reservations_legacy",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_case_review_reservations_org_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["organization_id", "reviewer_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_review_reservations_org_reviewer",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_case_review_reservations_active",
            "organization_id",
            "review_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reviewer_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    legacy_reservation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reviewer_reservations.id", ondelete="RESTRICT")
    )
    reviewer_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseReviewDecisionModel(Base):
    __tablename__ = "case_review_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approve', 'request_changes', 'reject', 'escalate')",
            name="ck_case_review_decisions_decision",
        ),
        CheckConstraint(
            "reviewer_role IN ('specialist', 'supervisor', 'administrator', 'auditor')",
            name="ck_case_review_decisions_reviewer_role",
        ),
        CheckConstraint(
            "(legacy_decision_id IS NULL AND reviewer_id IS NOT NULL) OR "
            "(legacy_decision_id IS NOT NULL AND reviewer_id IS NULL)",
            name="ck_case_review_decisions_lineage_actor",
        ),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_case_review_decisions_org_public"
        ),
        UniqueConstraint(
            "organization_id", "case_id", "review_id", name="uq_case_review_decisions_org_review"
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            "id",
            name="uq_case_review_decisions_org_review_id",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "review_id",
            "reservation_id",
            name="uq_case_review_decisions_org_reservation",
        ),
        UniqueConstraint("legacy_decision_id", name="uq_case_review_decisions_legacy"),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "review_id"],
            ["case_reviews.organization_id", "case_reviews.case_id", "case_reviews.id"],
            name="fk_case_review_decisions_org_review",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["organization_id", "reviewer_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_case_review_decisions_org_reviewer",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reviewer_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    legacy_decision_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("approval_decisions.id", ondelete="RESTRICT")
    )
    reviewer_public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
