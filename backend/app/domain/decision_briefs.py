from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.policies import EvidenceRetrievalStatus


class AnalysisStatus(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"


class DecisionGenerationStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CheckpointStatus(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"


class DecisionProposalState(StrEnum):
    DRAFT = "draft"
    INFORMATION_NEEDED = "information_needed"
    READY_FOR_REVIEW = "ready_for_review"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProposalConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskOutcome(StrEnum):
    PASSED = "passed"
    REQUIRES_REVIEW = "requires_review"
    INFORMATION_NEEDED = "information_needed"
    BLOCKED = "blocked"


class ResponseSuggestionStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    BLOCKED = "blocked"


class VerifiedFact(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    statement: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=300)
    verified_at: datetime


class InformationGap(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=1000)
    blocking: bool


class DecisionRiskCheck(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=300)
    outcome: RiskOutcome
    explanation: str = Field(min_length=1, max_length=1000)


class ProposedActionDraft(BaseModel):
    type: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=300)
    parameters: dict[str, str]
    impact_amount: Decimal | None = Field(default=None, ge=0)
    impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    expected_outcome: str = Field(min_length=1, max_length=1000)
    review_required: bool

    @model_validator(mode="after")
    def require_complete_impact(self) -> Self:
        if (self.impact_amount is None) != (self.impact_currency is None):
            raise ValueError("impact_amount and impact_currency must be supplied together")
        return self


class ProposedActionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    proposal_version_id: UUID
    type: str
    label: str
    parameters: dict[str, str]
    impact_amount: Decimal | None
    impact_currency: str | None
    expected_outcome: str
    review_required: bool
    created_at: datetime


class SuggestedResponseDraft(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10_000)
    status: ResponseSuggestionStatus


class SuggestedResponseRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    proposal_version_id: UUID
    subject: str
    body: str
    status: ResponseSuggestionStatus
    version: int
    created_at: datetime


class AnalysisCheckpointDraft(BaseModel):
    sequence: int = Field(ge=1)
    step: str = Field(min_length=1, max_length=64)
    status: CheckpointStatus
    summary: str = Field(min_length=1, max_length=1000)
    input_fingerprint: str = Field(min_length=64, max_length=64)
    output_fingerprint: str = Field(min_length=64, max_length=64)


class AnalysisCheckpointRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    analysis_run_id: UUID
    sequence: int
    step: str
    status: CheckpointStatus
    summary: str
    input_fingerprint: str
    output_fingerprint: str
    created_at: datetime


class DecisionAnalysis(BaseModel):
    status: AnalysisStatus
    policy_status: EvidenceRetrievalStatus
    facts: list[VerifiedFact]
    missing_information: list[InformationGap]
    risks: list[DecisionRiskCheck]
    outcome: str = Field(min_length=1, max_length=500)
    impact_amount: Decimal | None = Field(default=None, ge=0)
    impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    confidence: ProposalConfidence
    uncertainty: str = Field(min_length=1, max_length=1000)
    rationale: str = Field(min_length=1, max_length=2000)
    state: DecisionProposalState
    proposed_actions: list[ProposedActionDraft]
    response_draft: SuggestedResponseDraft
    checkpoints: list[AnalysisCheckpointDraft] = Field(min_length=1)
    risk_rule_version: str = Field(min_length=1, max_length=100)
    model_version: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)
    graph_version: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_complete_impact(self) -> Self:
        if (self.impact_amount is None) != (self.impact_currency is None):
            raise ValueError("impact_amount and impact_currency must be supplied together")
        return self


class EvidenceSnapshotReference(BaseModel):
    public_id: str = Field(min_length=1, max_length=64)
    fingerprint: str = Field(min_length=64, max_length=64)


class ContextSnapshotReference(BaseModel):
    public_id: str = Field(min_length=1, max_length=64)
    version: int = Field(ge=1)
    fingerprint: str = Field(min_length=64, max_length=64)


class DecisionBriefCreate(BaseModel):
    expected_case_version: int = Field(ge=1)
    input_fingerprint: str = Field(min_length=64, max_length=64)
    context_fingerprint: str = Field(min_length=64, max_length=64)
    evidence_fingerprint: str = Field(min_length=64, max_length=64)
    analysis: DecisionAnalysis
    evidence: list[EvidenceSnapshotReference]
    contexts: list[ContextSnapshotReference] = Field(min_length=1)


class DecisionGenerationLease(BaseModel):
    input_fingerprint: str = Field(min_length=64, max_length=64)
    owner_token: UUID
    fence_token: int = Field(ge=1)
    attempt: int = Field(ge=1)
    expires_at: datetime


class CompletedDecisionGeneration(BaseModel):
    input_fingerprint: str = Field(min_length=64, max_length=64)
    analysis_run_id: UUID


class LegacyDecisionBriefImport(BaseModel):
    legacy_proposal_version_id: UUID
    source_version: int = Field(ge=1)
    source_run_id: UUID
    input_fingerprint: str = Field(min_length=64, max_length=64)
    context_fingerprint: str = Field(min_length=64, max_length=64)
    evidence_fingerprint: str = Field(min_length=64, max_length=64)
    analysis: DecisionAnalysis
    created_at: datetime

    @model_validator(mode="after")
    def require_honest_compatibility_state(self) -> Self:
        if self.analysis.status is not AnalysisStatus.ABSTAINED:
            raise ValueError("legacy decision briefs must remain abstained")
        if self.analysis.policy_status is not EvidenceRetrievalStatus.MISSING:
            raise ValueError("legacy decision briefs cannot claim governed policy evidence")
        if self.analysis.state is not DecisionProposalState.INFORMATION_NEEDED:
            raise ValueError("legacy decision briefs must require fresh information")
        if self.analysis.confidence is not ProposalConfidence.LOW:
            raise ValueError("legacy decision briefs must retain low confidence")
        return self


class AnalysisRunRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    status: AnalysisStatus
    policy_status: EvidenceRetrievalStatus
    case_version: int
    input_fingerprint: str
    context_fingerprint: str
    evidence_fingerprint: str
    initiated_by: str
    model_version: str
    prompt_version: str
    graph_version: str
    risk_rule_version: str
    started_at: datetime
    completed_at: datetime


class CaseProposalRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    current_version: int
    state: DecisionProposalState
    version: int
    created_at: datetime
    updated_at: datetime


class CaseProposalVersionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    proposal_id: UUID
    analysis_run_id: UUID
    legacy_proposal_version_id: UUID | None
    version: int
    immutable: bool
    outcome: str
    impact_amount: Decimal | None
    impact_currency: str | None
    confidence: ProposalConfidence
    uncertainty: str
    rationale: str
    state: DecisionProposalState
    facts: list[VerifiedFact]
    missing_information: list[InformationGap]
    risks: list[DecisionRiskCheck]
    evidence_ids: list[str]
    context_snapshot_ids: list[str]
    evidence_fingerprint: str
    context_fingerprint: str
    risk_fingerprint: str
    risk_rule_version: str
    model_version: str
    prompt_version: str
    graph_version: str
    created_at: datetime


class DecisionBriefRecord(BaseModel):
    run: AnalysisRunRecord
    proposal: CaseProposalRecord
    version: CaseProposalVersionRecord
    proposed_actions: list[ProposedActionRecord]
    response_draft: SuggestedResponseRecord
    checkpoints: list[AnalysisCheckpointRecord]


class ProposalNotFound(LookupError):
    pass


class ProposalConcurrencyConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The proposal changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


class ProposalSnapshotMismatch(RuntimeError):
    pass


class ProposalGenerationNotAllowed(RuntimeError):
    pass


class DecisionGenerationInProgress(RuntimeError):
    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__("An identical decision brief is already being generated.")
        self.retry_after_seconds = max(1, retry_after_seconds)


class DecisionGenerationRetryExhausted(RuntimeError):
    pass


class DecisionGenerationLeaseLost(RuntimeError):
    pass


class DecisionFingerprintRetryExhausted(RuntimeError):
    pass
