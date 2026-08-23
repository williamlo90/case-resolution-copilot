from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.retrieval_v2 import EmbeddingProfileRecord, PolicyIndexJobRecord


class PolicyIndexClauseRecord(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: UUID
    organization_id: UUID
    policy_id: UUID
    policy_version_id: UUID
    sequence: int = Field(ge=1)
    text: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class PolicyIndexWorkItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    job: PolicyIndexJobRecord
    profile: EmbeddingProfileRecord
    clauses: tuple[PolicyIndexClauseRecord, ...]
    lease_expires_at: datetime


class PolicyIndexDrainResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    claimed_jobs: int = Field(ge=0)
    completed_jobs: int = Field(ge=0)
    failed_jobs: int = Field(ge=0)
    indexed_clauses: int = Field(ge=0)
    skipped_clauses: int = Field(ge=0)
