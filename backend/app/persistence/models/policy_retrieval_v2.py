from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class PolicyEmbeddingProfileModel(Base):
    __tablename__ = "policy_embedding_profiles"
    __table_args__ = (
        CheckConstraint("dimensions = 512", name="ck_policy_embedding_profiles_dimensions"),
        CheckConstraint(
            "status IN ('building', 'ready', 'active', 'retired', 'failed')",
            name="ck_policy_embedding_profiles_status",
        ),
        CheckConstraint(
            "expected_clause_count >= 0 AND indexed_clause_count >= 0",
            name="ck_policy_embedding_profiles_counts",
        ),
        UniqueConstraint("profile_key", name="uq_policy_embedding_profiles_key"),
        Index(
            "uq_policy_embedding_profiles_active_environment",
            "environment",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_key: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(64), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(64), nullable=False)
    index_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_clause_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    indexed_clause_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    build_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by: Mapped[str | None] = mapped_column(String(64))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GovernedPolicyClauseEmbeddingV2Model(Base):
    __tablename__ = "governed_policy_clause_embeddings_v2"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "clause_id",
            "profile_id",
            name="uq_policy_clause_embeddings_v2_org_clause_profile",
        ),
        ForeignKeyConstraint(
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
        Index(
            "ix_policy_clause_embeddings_v2_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
        Index(
            "ix_policy_clause_embeddings_v2_tenant_profile",
            "organization_id",
            "profile_id",
            "clause_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    clause_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_embedding_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(512), nullable=False)
    provider_request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class PolicyIndexJobModel(Base):
    __tablename__ = "policy_index_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'dead')",
            name="ck_policy_index_jobs_status",
        ),
        CheckConstraint("page_budget BETWEEN 1 AND 32", name="ck_policy_index_jobs_budget"),
        CheckConstraint("attempt_count >= 0", name="ck_policy_index_jobs_attempts"),
        CheckConstraint(
            "indexed_clause_count >= 0 AND skipped_clause_count >= 0",
            name="ck_policy_index_jobs_counts",
        ),
        CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL AND "
            "lease_expires_at IS NOT NULL) OR status <> 'running'",
            name="ck_policy_index_jobs_running_lease",
        ),
        UniqueConstraint("job_key", name="uq_policy_index_jobs_key"),
        UniqueConstraint(
            "organization_id", "public_id", name="uq_policy_index_jobs_org_public"
        ),
        ForeignKeyConstraint(
            ["organization_id", "policy_id", "policy_version_id"],
            [
                "governed_policy_versions.organization_id",
                "governed_policy_versions.policy_id",
                "governed_policy_versions.id",
            ],
            name="fk_policy_index_jobs_version",
            ondelete="CASCADE",
        ),
        Index("ix_policy_index_jobs_claim", "status", "available_at", "lease_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    profile_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_embedding_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    job_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    page_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    indexed_clause_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_clause_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
