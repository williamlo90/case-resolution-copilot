from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.cases import CaseCategory


class RetrievalEvidenceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    proposal_id: UUID
    policy_version_id: UUID
    chunk_id: UUID
    source_id: str
    clause: str
    excerpt: str
    content_hash: str
    effective_from: date
    retrieval_score: float
    corpus_version: str
    chunking_version: str
    embedding_version: str
    index_version: str
    created_at: datetime


class PolicyDocumentVersionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: str
    version: int
    title: str
    case_category: str
    plan: str
    jurisdiction: str
    customer_tier: str
    effective_from: date
    effective_to: date | None
    lifecycle_status: str
    content_hash: str
    corpus_version: str
    created_at: datetime


class PolicyLifecycleStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    RETIRED = "retired"
    EXPIRED = "expired"
    CONFLICTING = "conflicting"
    PARSING_FAILED = "parsing_failed"


class PolicyVersionStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    RETIRED = "retired"


class PolicySourceKind(StrEnum):
    UPLOAD = "upload"
    URL = "url"
    MANUAL = "manual"


class EvidenceRetrievalStatus(StrEnum):
    RELEVANT = "relevant"
    MISSING = "missing"
    STALE = "stale"
    CONFLICTING = "conflicting"
    INAPPLICABLE = "inapplicable"


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    return value


class PolicyApplicability(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_scope: str = Field(min_length=1, max_length=100)
    case_categories: list[str] = Field(min_length=1)
    products: list[str] = Field(min_length=1)
    regions: list[str] = Field(min_length=1)
    channels: list[str] = Field(min_length=1)
    customer_tiers: list[str] = Field(min_length=1)

    @field_validator(
        "decision_scope",
        "products",
        "regions",
        "channels",
        "customer_tiers",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        if isinstance(value, list):
            normalized = [str(item).strip().lower() for item in value]
            if any(not item for item in normalized):
                raise ValueError("applicability values cannot be blank")
            return list(dict.fromkeys(normalized))
        return value

    @field_validator("case_categories", mode="before")
    @classmethod
    def normalize_categories(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized = [str(item).strip().lower() for item in value]
        if any(not item for item in normalized):
            raise ValueError("case categories cannot be blank")
        allowed = {category.value for category in CaseCategory} | {"all"}
        if not set(normalized) <= allowed:
            raise ValueError("case category is not supported")
        return list(dict.fromkeys(normalized))


class ParsedPolicyClause(BaseModel):
    heading: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=20)
    applies_when: str = Field(min_length=1)


class IndexedPolicyClause(BaseModel):
    clause: ParsedPolicyClause
    embedding_version: str = Field(min_length=1, max_length=64)
    embedding: list[float] = Field(min_length=32, max_length=32)


class PolicyDraftContent(BaseModel):
    source_text: str = Field(min_length=20, max_length=200_000)
    applicability: PolicyApplicability
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    @field_validator("effective_from", "effective_to")
    @classmethod
    def require_utc(cls, value: datetime | None, info: object) -> datetime | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "timestamp")
        return _require_utc(value, str(field_name))

    @model_validator(mode="after")
    def require_effective_order(self) -> Self:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("effective_to must be after effective_from")
        return self


class PolicyCreate(BaseModel):
    public_id: str = Field(pattern=r"^POL-[A-Z0-9-]+$", max_length=64)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=1000)
    source_kind: PolicySourceKind
    source_name: str = Field(min_length=1, max_length=500)
    content: PolicyDraftContent | None


class PolicyRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    title: str
    description: str
    status: PolicyLifecycleStatus
    owner_id: UUID
    source_kind: PolicySourceKind
    source_name: str
    source_error: str | None
    current_version: int
    version: int
    created_at: datetime
    updated_at: datetime


class PolicyOwnerRecord(BaseModel):
    id: UUID
    public_id: str
    name: str


class GovernedPolicyVersionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    policy_id: UUID
    legacy_policy_version_id: UUID | None
    version: int
    record_version: int
    status: PolicyVersionStatus
    immutable: bool
    source_text: str
    content_hash: str
    decision_scope: str
    case_categories: list[str]
    products: list[str]
    regions: list[str]
    channels: list[str]
    customer_tiers: list[str]
    effective_from: datetime | None
    effective_to: datetime | None
    created_by: str
    created_at: datetime
    submitted_at: datetime | None
    published_at: datetime | None
    retired_at: datetime | None

    def applicability(self) -> PolicyApplicability:
        return PolicyApplicability(
            decision_scope=self.decision_scope,
            case_categories=self.case_categories,
            products=self.products,
            regions=self.regions,
            channels=self.channels,
            customer_tiers=self.customer_tiers,
        )


class GovernedPolicyClauseRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    policy_id: UUID
    policy_version_id: UUID
    sequence: int
    heading: str
    text: str
    applies_when: str
    content_hash: str
    chunking_version: str
    embedding_version: str
    index_version: str
    embedding: list[float]


class CasePolicyEvidenceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    policy_id: UUID
    policy_version_id: UUID
    clause_id: UUID
    citation: str
    excerpt: str
    applicability: str
    fingerprint: str
    freshness: str
    conflict_state: str
    retrieval_score: float
    policy_content_hash: str
    clause_content_hash: str
    effective_from: datetime | None
    effective_to: datetime | None
    corpus_version: str
    chunking_version: str
    embedding_version: str
    index_version: str
    embedding_profile_key: str | None = None
    retrieval_algorithm_version: str | None = None
    query_fingerprint: str | None = None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    fused_retrieval_score: float | None = None
    retrieval_run_correlation_id: str | None = None
    recorded_at: datetime


class PolicyEvidenceUsageRecord(BaseModel):
    evidence: CasePolicyEvidenceRecord
    case_public_id: str


class PolicyVersionBundle(BaseModel):
    version: GovernedPolicyVersionRecord
    clauses: list[GovernedPolicyClauseRecord]
    evidence: list[PolicyEvidenceUsageRecord]


class PolicyWorkspaceRecord(BaseModel):
    policy: PolicyRecord
    owner: PolicyOwnerRecord
    versions: list[PolicyVersionBundle]


class PolicyListItemRecord(BaseModel):
    policy: PolicyRecord
    owner: PolicyOwnerRecord
    current_version: GovernedPolicyVersionRecord | None
    used_by_cases: int


class PolicyListPageRecord(BaseModel):
    items: list[PolicyListItemRecord]
    next_offset: int | None
    total: int


class PolicyCandidateRecord(BaseModel):
    policy: PolicyRecord
    version: GovernedPolicyVersionRecord
    clauses: list[GovernedPolicyClauseRecord]


class RankedPolicyCandidateRecord(BaseModel):
    candidate: PolicyCandidateRecord
    retrieval_score: float = Field(ge=-1, le=1)


class PolicyRetrievalCandidatePage(BaseModel):
    category_matches: int = Field(ge=0)
    applicable_matches: int = Field(ge=0)
    active_matches: int = Field(ge=0)
    truncated: bool
    conflicting_scopes: list[str] = Field(default_factory=list)
    candidates: list[RankedPolicyCandidateRecord]

    @model_validator(mode="after")
    def require_honest_truncation(self) -> Self:
        if self.truncated and self.candidates:
            raise ValueError("truncated retrieval candidates must fail closed before ranking")
        return self


class PolicyEvidenceBundle(BaseModel):
    evidence: CasePolicyEvidenceRecord
    policy: PolicyRecord
    version: GovernedPolicyVersionRecord
    clause: GovernedPolicyClauseRecord


class PolicyEvidenceBinding(BaseModel):
    policy: PolicyRecord
    version: GovernedPolicyVersionRecord
    clause: GovernedPolicyClauseRecord
    retrieval_score: float
    applicability: str
    fingerprint: str
    embedding_profile_key: str | None = None
    retrieval_algorithm_version: str | None = None
    query_fingerprint: str | None = None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    fused_retrieval_score: float | None = None
    retrieval_run_correlation_id: str | None = None


class LegacyPolicyClauseImport(BaseModel):
    public_id: str
    sequence: int
    heading: str
    text: str
    applies_when: str
    content_hash: str
    chunking_version: str
    embedding_version: str
    index_version: str
    embedding: list[float]


class LegacyPolicyImport(BaseModel):
    public_id: str
    legacy_policy_version_id: UUID
    source_id: str
    version: int
    title: str
    description: str
    status: PolicyVersionStatus
    source_text: str
    content_hash: str
    applicability: PolicyApplicability
    effective_from: datetime
    effective_to: datetime | None
    created_at: datetime
    clauses: list[LegacyPolicyClauseImport] = Field(min_length=1)


class EvidenceRetrievalResult(BaseModel):
    status: EvidenceRetrievalStatus
    reason: str
    evidence: list[PolicyEvidenceBundle]


class PolicyNotFound(LookupError):
    pass


class PolicyConcurrencyConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The policy changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


class PolicyVersionConcurrencyConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The policy version changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


class InvalidPolicyTransition(ValueError):
    pass


class PolicySourceParseError(ValueError):
    pass


class PolicyActorNotAssignable(LookupError):
    pass


class PolicyAlreadyExists(RuntimeError):
    pass
