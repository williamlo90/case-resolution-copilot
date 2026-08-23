from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class PolicyModel(Base):
    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint("current_version >= 0", name="ck_policies_current_version"),
        CheckConstraint("version > 0", name="ck_policies_version_positive"),
        CheckConstraint(
            "status IN ('draft', 'in_review', 'published', 'scheduled', 'retired', "
            "'expired', 'conflicting', 'parsing_failed')",
            name="ck_policies_status",
        ),
        CheckConstraint(
            "source_kind IN ('upload', 'url', 'manual')", name="ck_policies_source_kind"
        ),
        UniqueConstraint("organization_id", "id", name="uq_policies_org_id"),
        UniqueConstraint("organization_id", "public_id", name="uq_policies_org_public"),
        ForeignKeyConstraint(
            ["organization_id", "owner_id"],
            ["memberships.organization_id", "memberships.id"],
            name="fk_policies_org_owner_memberships",
            ondelete="RESTRICT",
        ),
        Index("ix_policies_org_status_updated", "organization_id", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_error: Mapped[str | None] = mapped_column(Text)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class GovernedPolicyVersionModel(Base):
    __tablename__ = "governed_policy_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_governed_policy_versions_version"),
        CheckConstraint("record_version > 0", name="ck_governed_policy_versions_record_version"),
        CheckConstraint(
            "status IN ('draft', 'in_review', 'published', 'scheduled', 'retired')",
            name="ck_governed_policy_versions_status",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from",
            name="ck_governed_policy_versions_effective_order",
        ),
        UniqueConstraint(
            "organization_id",
            "policy_id",
            "version",
            name="uq_governed_versions_org_policy_version",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_governed_versions_org_public"),
        UniqueConstraint(
            "organization_id", "policy_id", "id", name="uq_governed_versions_org_policy_id"
        ),
        UniqueConstraint("legacy_policy_version_id", name="uq_governed_versions_legacy_version"),
        ForeignKeyConstraint(
            ["organization_id", "policy_id"],
            ["policies.organization_id", "policies.id"],
            name="fk_governed_versions_org_policy",
            ondelete="CASCADE",
        ),
        Index(
            "ix_governed_versions_org_status_effective",
            "organization_id",
            "status",
            "effective_from",
        ),
        Index(
            "ix_policy_versions_case_categories_gin",
            "case_categories",
            postgresql_using="gin",
            postgresql_ops={"case_categories": "jsonb_path_ops"},
        ),
        Index(
            "ix_policy_versions_products_gin",
            "products",
            postgresql_using="gin",
            postgresql_ops={"products": "jsonb_path_ops"},
        ),
        Index(
            "ix_policy_versions_regions_gin",
            "regions",
            postgresql_using="gin",
            postgresql_ops={"regions": "jsonb_path_ops"},
        ),
        Index(
            "ix_policy_versions_channels_gin",
            "channels",
            postgresql_using="gin",
            postgresql_ops={"channels": "jsonb_path_ops"},
        ),
        Index(
            "ix_policy_versions_customer_tiers_gin",
            "customer_tiers",
            postgresql_using="gin",
            postgresql_ops={"customer_tiers": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    legacy_policy_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("policy_document_versions.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_scope: Mapped[str] = mapped_column(String(100), nullable=False)
    case_categories: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    products: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    regions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    channels: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    customer_tiers: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GovernedPolicyClauseModel(Base):
    __tablename__ = "governed_policy_clauses"
    __table_args__ = (
        CheckConstraint("sequence > 0", name="ck_governed_policy_clauses_sequence"),
        UniqueConstraint("organization_id", "public_id", name="uq_governed_clauses_org_public"),
        UniqueConstraint(
            "organization_id",
            "policy_version_id",
            "sequence",
            name="uq_governed_clauses_org_version_sequence",
        ),
        UniqueConstraint(
            "organization_id",
            "policy_id",
            "policy_version_id",
            "id",
            name="uq_governed_clauses_org_policy_version_id",
        ),
        ForeignKeyConstraint(
            ["organization_id", "policy_id", "policy_version_id"],
            [
                "governed_policy_versions.organization_id",
                "governed_policy_versions.policy_id",
                "governed_policy_versions.id",
            ],
            name="fk_governed_clauses_org_policy_version",
            ondelete="CASCADE",
        ),
        Index(
            "ix_policy_clauses_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
        Index(
            "ix_governed_policy_clauses_search_vector_gin",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(300), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    applies_when: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(64), nullable=False)
    index_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(32), nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(heading, '') || ' ' || "
            "coalesce(text, '') || ' ' || coalesce(applies_when, ''))",
            persisted=True,
        ),
        nullable=False,
    )


class CasePolicyEvidenceModel(Base):
    __tablename__ = "case_policy_evidence"
    __table_args__ = (
        CheckConstraint(
            "freshness IN ('current', 'stale')", name="ck_case_policy_evidence_freshness"
        ),
        CheckConstraint(
            "conflict_state IN ('none', 'possible', 'confirmed')",
            name="ck_case_policy_evidence_conflict",
        ),
        CheckConstraint(
            "retrieval_score >= -1 AND retrieval_score <= 1",
            name="ck_case_policy_evidence_score",
        ),
        CheckConstraint(
            "fused_retrieval_score IS NULL OR fused_retrieval_score >= 0",
            name="ck_case_policy_evidence_fused_score",
        ),
        UniqueConstraint("organization_id", "public_id", name="uq_case_policy_evidence_org_public"),
        UniqueConstraint("organization_id", "id", name="uq_case_policy_evidence_org_id"),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "id",
            name="uq_case_policy_evidence_org_case_id",
        ),
        UniqueConstraint(
            "organization_id",
            "case_id",
            "fingerprint",
            name="uq_case_policy_evidence_org_case_fingerprint",
        ),
        ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["cases.organization_id", "cases.id"],
            name="fk_case_policy_evidence_org_case",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "policy_id"],
            ["policies.organization_id", "policies.id"],
            name="fk_case_policy_evidence_org_policy",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "policy_id", "policy_version_id"],
            [
                "governed_policy_versions.organization_id",
                "governed_policy_versions.policy_id",
                "governed_policy_versions.id",
            ],
            name="fk_case_policy_evidence_org_policy_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "policy_id", "policy_version_id", "clause_id"],
            [
                "governed_policy_clauses.organization_id",
                "governed_policy_clauses.policy_id",
                "governed_policy_clauses.policy_version_id",
                "governed_policy_clauses.id",
            ],
            name="fk_case_policy_evidence_org_clause",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_case_policy_evidence_org_case_recorded",
            "organization_id",
            "case_id",
            "recorded_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    public_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    clause_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    citation: Mapped[str] = mapped_column(String(500), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    applicability: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    freshness: Mapped[str] = mapped_column(String(16), nullable=False)
    conflict_state: Mapped[str] = mapped_column(String(16), nullable=False)
    retrieval_score: Mapped[float] = mapped_column(nullable=False)
    policy_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    clause_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    corpus_version: Mapped[str] = mapped_column(String(64), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(64), nullable=False)
    index_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_profile_key: Mapped[str | None] = mapped_column(String(100))
    retrieval_algorithm_version: Mapped[str | None] = mapped_column(String(64))
    query_fingerprint: Mapped[str | None] = mapped_column(String(64))
    dense_rank: Mapped[int | None] = mapped_column(Integer)
    lexical_rank: Mapped[int | None] = mapped_column(Integer)
    fused_retrieval_score: Mapped[float | None] = mapped_column()
    retrieval_run_correlation_id: Mapped[str | None] = mapped_column(String(100))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
