from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utc_now


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_tasks_version_positive"),
        CheckConstraint("task_type = 'refund'", name="ck_tasks_supported_type"),
        CheckConstraint(
            "status IN ('queued', 'running', 'waiting_approval', 'completed_verified', "
            "'failed_no_side_effect', 'execution_uncertain', 'reconciling', 'escalated')",
            name="ck_tasks_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    summary: Mapped[str] = mapped_column(String(240), nullable=False, default="Refund request")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exposure_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    exposure_currency: Mapped[str | None] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    request: Mapped["RequestModel"] = relationship(
        back_populates="task", cascade="all, delete-orphan", uselist=False
    )
    runs: Mapped[list["AgentRunModel"]] = relationship(back_populates="task")


class RequestModel(Base):
    __tablename__ = "requests"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_requests_task_id"),
        CheckConstraint("channel IN ('email', 'chat', 'phone')", name="ck_requests_channel"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_message: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)

    task: Mapped[TaskModel] = relationship(back_populates="request")


class AgentRunModel(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_agent_runs_version_positive"),
        CheckConstraint(
            "status IN ('queued', 'running', 'waiting_approval', 'completed_verified', "
            "'failed_no_side_effect', 'execution_uncertain', 'reconciling', 'escalated')",
            name="ck_agent_runs_status",
        ),
        Index("ix_agent_runs_task_created", "task_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    graph_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    task: Mapped[TaskModel] = relationship(back_populates="runs")
    tool_attempts: Mapped[list["ToolAttemptModel"]] = relationship(back_populates="run")


class CustomerSnapshotModel(Base):
    __tablename__ = "customer_snapshots"
    __table_args__ = (UniqueConstraint("task_id", name="uq_customer_snapshots_task_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    contact: Mapped[str] = mapped_column(String(254), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class BookingSnapshotModel(Base):
    __tablename__ = "booking_snapshots"
    __table_args__ = (UniqueConstraint("task_id", name="uq_booking_snapshots_task_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    service_date_label: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    itinerary: Mapped[str] = mapped_column(String(240), nullable=False)
    passengers: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ToolAttemptModel(Base):
    __tablename__ = "tool_attempts"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('succeeded', 'rejected', 'uncertain')",
            name="ck_tool_attempts_outcome",
        ),
        CheckConstraint(
            "side_effect_state IN ('not_attempted', 'none', 'confirmed', 'possible')",
            name="ck_tool_attempts_side_effect_state",
        ),
        Index("ix_tool_attempts_run_started", "run_id", "started_at"),
        Index("ix_tool_attempts_idempotency", "tool_name", "idempotency_key"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="RESTRICT"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    side_effect_state: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    run: Mapped[AgentRunModel] = relationship(back_populates="tool_attempts")
    receipt: Mapped["ExternalReceiptModel | None"] = relationship(
        back_populates="tool_attempt", uselist=False
    )


class ExternalReceiptModel(Base):
    __tablename__ = "external_receipts"
    __table_args__ = (
        UniqueConstraint("tool_attempt_id", name="uq_external_receipts_tool_attempt_id"),
        UniqueConstraint(
            "provider",
            "tool_name",
            "idempotency_key",
            name="uq_external_receipts_provider_tool_idempotency",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tool_attempt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tool_attempts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    external_reference: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    tool_attempt: Mapped[ToolAttemptModel] = relationship(back_populates="receipt")


class RiskDecisionModel(Base):
    __tablename__ = "risk_decisions"
    __table_args__ = (UniqueConstraint("run_id", name="uq_risk_decisions_run_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="RESTRICT"), nullable=False
    )
    requires_approval: Mapped[bool] = mapped_column(nullable=False)
    risk_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ProposalVersionModel(Base):
    __tablename__ = "proposal_versions"
    __table_args__ = (
        UniqueConstraint("task_id", "version", name="uq_proposal_versions_task_version"),
        UniqueConstraint("run_id", name="uq_proposal_versions_run_id"),
        CheckConstraint("version > 0", name="ck_proposal_versions_version_positive"),
        CheckConstraint(
            "status IN ('draft_waiting_evidence', 'waiting_approval')",
            name="ck_proposal_versions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    proposal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    proposed_outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    draft_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    expected_postcondition: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class PolicyDocumentVersionModel(Base):
    __tablename__ = "policy_document_versions"
    __table_args__ = (
        UniqueConstraint("source_id", "version", name="uq_policy_source_version"),
        CheckConstraint(
            "lifecycle_status IN ('active', 'quarantined')",
            name="ck_policy_lifecycle_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    case_category: Mapped[str] = mapped_column(String(64), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(16), nullable=False)
    customer_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_from: Mapped[date] = mapped_column(nullable=False)
    effective_to: Mapped[date | None] = mapped_column()
    lifecycle_status: Mapped[str] = mapped_column(String(16), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    corpus_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class PolicyChunkModel(Base):
    __tablename__ = "policy_chunks"
    __table_args__ = (
        UniqueConstraint("policy_version_id", "clause", name="uq_policy_chunk_clause"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_document_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    clause: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(64), nullable=False)
    index_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(32), nullable=False)


class RetrievalEvidenceModel(Base):
    __tablename__ = "retrieval_evidence"
    __table_args__ = (
        UniqueConstraint("proposal_id", "chunk_id", name="uq_evidence_proposal_chunk"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("proposal_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_document_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("policy_chunks.id", ondelete="RESTRICT"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    clause: Mapped[str] = mapped_column(String(64), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(nullable=False)
    retrieval_score: Mapped[float] = mapped_column(nullable=False)
    corpus_version: Mapped[str] = mapped_column(String(64), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(64), nullable=False)
    index_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ReviewerReservationModel(Base):
    __tablename__ = "reviewer_reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'consumed', 'expired')",
            name="ck_reviewer_reservations_status",
        ),
        Index(
            "uq_reviewer_reservations_active_proposal",
            "proposal_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("proposal_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(32), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalDecisionModel(Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('approved', 'rejected', 'needs_information')",
            name="ck_approval_decisions_outcome",
        ),
        UniqueConstraint("proposal_id", name="uq_approval_decisions_proposal"),
        UniqueConstraint("reservation_id", name="uq_approval_decisions_reservation"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("proposal_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reservation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reviewer_reservations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(32), nullable=False)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
