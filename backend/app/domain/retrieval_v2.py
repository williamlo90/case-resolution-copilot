from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.policies import PolicyCandidateRecord


class EmbeddingProfileStatus(StrEnum):
    BUILDING = "building"
    READY = "ready"
    ACTIVE = "active"
    RETIRED = "retired"
    FAILED = "failed"


class PolicyIndexJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


class EmbeddingProfileRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_key: str
    environment: str
    provider: str
    model: str
    dimensions: int
    normalization_version: str
    chunking_version: str
    index_version: str
    status: EmbeddingProfileStatus
    expected_clause_count: int
    indexed_clause_count: int
    build_fingerprint: str
    created_at: datetime
    ready_at: datetime | None
    activated_by: str | None
    retired_at: datetime | None


class PolicyIndexJobRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    profile_id: UUID
    policy_id: UUID
    policy_version_id: UUID
    source_content_fingerprint: str
    job_key: str
    status: PolicyIndexJobStatus
    page_budget: int
    attempt_count: int
    available_at: datetime
    lease_owner: str | None
    lease_expires_at: datetime | None
    last_error_code: str | None
    indexed_clause_count: int
    skipped_clause_count: int
    completed_at: datetime | None
    created_at: datetime


class RankedClause(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate: PolicyCandidateRecord
    dense_rank: int | None = Field(default=None, ge=1)
    lexical_rank: int | None = Field(default=None, ge=1)
    fused_score: float = Field(ge=0)

    @model_validator(mode="after")
    def require_a_source_rank(self) -> "RankedClause":
        if self.dense_rank is None and self.lexical_rank is None:
            raise ValueError("A fused clause requires a dense or lexical rank.")
        if len(self.candidate.clauses) != 1:
            raise ValueError("A ranked clause must contain exactly one clause.")
        return self


class MinimizedPolicyQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=4000)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    omitted_fields: tuple[str, ...] = ()


class HybridPolicyCandidatePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_key: str
    index_ready: bool
    category_matches: int = Field(ge=0)
    applicable_matches: int = Field(ge=0)
    active_matches: int = Field(ge=0)
    conflicting_scopes: tuple[str, ...] = ()
    dense: tuple[PolicyCandidateRecord, ...] = ()
    lexical: tuple[PolicyCandidateRecord, ...] = ()

    @model_validator(mode="after")
    def fail_closed_when_index_is_incomplete(self) -> "HybridPolicyCandidatePage":
        if not self.index_ready and (self.dense or self.lexical):
            raise ValueError("An incomplete policy index cannot return ranked clauses.")
        return self
