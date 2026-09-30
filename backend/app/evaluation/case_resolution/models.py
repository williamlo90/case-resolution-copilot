from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.cases import (
    BusinessObjectType,
    CaseCategory,
    CaseRisk,
    CaseUrgency,
    CustomerTier,
    RequestChannel,
    SourceFreshness,
)
from app.domain.decision_briefs import (
    AnalysisStatus,
    DecisionAnalysis,
    DecisionProposalState,
    ProposalConfidence,
    ResponseSuggestionStatus,
    RiskOutcome,
)
from app.domain.policies import EvidenceRetrievalStatus, PolicyVersionStatus
from app.domain.reviews import ReviewDecision


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BenchmarkCategory(StrEnum):
    COMMON = "common"
    MISSING_INFORMATION = "missing_information"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    POLICY_HEAVY = "policy_heavy"
    NOISY_EVIDENCE = "noisy_evidence"
    ADVERSARIAL_SAFETY = "adversarial_safety"


class BenchmarkDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class BusinessEvidenceFixture(StrictFrozenModel):
    public_id: str = Field(pattern=r"^EVD-CRV1-\d{3}-[A-Z0-9-]+$", max_length=64)
    type: BusinessObjectType
    label: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=100)
    source_reference: str = Field(min_length=1, max_length=300)
    status: str = Field(min_length=1, max_length=100)
    fields: dict[str, str] = Field(default_factory=dict)
    captured_at: datetime
    source_freshness: SourceFreshness
    source_checked_at: datetime


class GovernedPolicyFixture(StrictFrozenModel):
    policy_public_id: str = Field(pattern=r"^POL-[A-Z0-9-]+$", max_length=64)
    version: int = Field(ge=1)
    version_status: PolicyVersionStatus
    clause_public_id: str = Field(pattern=r"^POLC-[A-Z0-9-]+$", max_length=64)
    heading: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=20, max_length=10_000)
    applies_when: str = Field(min_length=1, max_length=1000)
    decision_scope: str = Field(min_length=1, max_length=100)
    case_categories: tuple[str, ...] = Field(min_length=1)
    products: tuple[str, ...] = Field(min_length=1)
    regions: tuple[str, ...] = Field(min_length=1)
    channels: tuple[str, ...] = Field(min_length=1)
    customer_tiers: tuple[str, ...] = Field(min_length=1)
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def require_effective_order(self) -> Self:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ValueError("Policy effective_to must be after effective_from.")
        return self


class CaseResolutionBenchmarkCase(StrictFrozenModel):
    case_id: str = Field(pattern=r"^CRV1-\d{3}$")
    public_case_id: str = Field(pattern=r"^CS-EVAL-\d{3}$", max_length=64)
    benchmark_category: BenchmarkCategory
    difficulty: BenchmarkDifficulty
    scenario: str = Field(min_length=1, max_length=1000)
    customer_request: str = Field(min_length=1, max_length=5000)
    request_summary: str = Field(min_length=1, max_length=1000)
    category: CaseCategory
    urgency: CaseUrgency
    risk: CaseRisk
    channel: RequestChannel
    customer_tier: CustomerTier
    product: str = Field(min_length=1, max_length=100)
    region: str = Field(min_length=2, max_length=100)
    external_reference: str = Field(min_length=1, max_length=300)
    impact_amount: Decimal | None = Field(default=None, ge=0)
    impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    source_freshness: SourceFreshness
    source_checked_at: datetime
    as_of: datetime
    available_evidence: tuple[BusinessEvidenceFixture, ...]
    available_policy_context: tuple[GovernedPolicyFixture, ...]

    @model_validator(mode="after")
    def require_consistent_case(self) -> Self:
        if (self.impact_amount is None) != (self.impact_currency is None):
            raise ValueError("Impact amount and currency must be supplied together.")
        evidence_ids = [item.public_id for item in self.available_evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence IDs must be unique within a benchmark case.")
        clause_ids = [item.clause_public_id for item in self.available_policy_context]
        if len(clause_ids) != len(set(clause_ids)):
            raise ValueError("Policy clause IDs must be unique within a benchmark case.")
        return self


class RequiredPolicyReference(StrictFrozenModel):
    policy_public_id: str = Field(pattern=r"^POL-[A-Z0-9-]+$", max_length=64)
    version: int = Field(ge=1)
    clause_public_id: str = Field(pattern=r"^POLC-[A-Z0-9-]+$", max_length=64)


class RequiredInformationGap(StrictFrozenModel):
    label: str = Field(min_length=1, max_length=300)
    blocking: Literal[True]


class RequiredRiskOutcome(StrictFrozenModel):
    label: Literal[
        "Policy authority",
        "Source freshness",
        "Information completeness",
        "Human authority",
    ]
    outcome: RiskOutcome


class RequiredAction(StrictFrozenModel):
    type: str = Field(min_length=1, max_length=100)
    parameters: dict[str, str] = Field(default_factory=dict)
    impact_amount: Decimal | None = Field(default=None, ge=0)
    impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    review_required: bool

    @model_validator(mode="after")
    def require_complete_impact(self) -> Self:
        if (self.impact_amount is None) != (self.impact_currency is None):
            raise ValueError("Action impact amount and currency must be supplied together.")
        return self


class ExpectedReviewBoundary(StrictFrozenModel):
    submission_allowed: bool
    required_role: Literal["none", "supervisor", "administrator"]
    allowed_decisions: tuple[ReviewDecision, ...]
    execution_eligible: bool


class CaseResolutionBenchmarkLabel(StrictFrozenModel):
    case_id: str = Field(pattern=r"^CRV1-\d{3}$")
    expected_resolution: str = Field(min_length=1, max_length=1000)
    expected_analysis_status: AnalysisStatus
    expected_policy_status: EvidenceRetrievalStatus
    expected_proposal_state: DecisionProposalState
    expected_response_status: ResponseSuggestionStatus
    expected_confidence: ProposalConfidence
    expected_impact_amount: Decimal | None = Field(default=None, ge=0)
    expected_impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    required_evidence_ids: tuple[str, ...]
    required_policy_references: tuple[RequiredPolicyReference, ...]
    required_fact_fragments: tuple[str, ...] = ()
    required_information_gaps: tuple[RequiredInformationGap, ...] = ()
    required_risk_outcomes: tuple[RequiredRiskOutcome, ...] = Field(min_length=4, max_length=4)
    forbidden_claims: tuple[str, ...] = Field(min_length=1)
    should_escalate: bool
    required_actions: tuple[RequiredAction, ...] = Field(min_length=1)
    forbidden_actions: tuple[str, ...] = Field(min_length=1)
    expected_review_required: bool
    expected_review: ExpectedReviewBoundary
    notes_for_grader: str = Field(min_length=1, max_length=3000)
    review_status: Literal["approved"]
    reviewed_by_role: Literal["independent_gold_label_reviewer"]

    @model_validator(mode="after")
    def require_noncontradictory_actions(self) -> Self:
        if (self.expected_impact_amount is None) != (self.expected_impact_currency is None):
            raise ValueError("Expected impact amount and currency must be supplied together.")
        overlap = {item.type for item in self.required_actions} & set(self.forbidden_actions)
        if overlap:
            raise ValueError(f"Required and forbidden actions overlap: {sorted(overlap)}.")
        risk_labels = [item.label for item in self.required_risk_outcomes]
        if len(risk_labels) != len(set(risk_labels)):
            raise ValueError("Required risk labels must be unique.")
        if self.expected_review_required != any(
            item.review_required for item in self.required_actions
        ):
            raise ValueError("Expected review flag must match the required consequential action.")
        return self


class CaseResolutionBenchmarkInputSuite(StrictFrozenModel):
    version: Literal["case-resolution-input-v1"]
    source: Literal["synthetic_case_resolution_suite"]
    cases: tuple[CaseResolutionBenchmarkCase, ...] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def require_frozen_composition(self) -> Self:
        ids = [case.case_id for case in self.cases]
        public_ids = [case.public_case_id for case in self.cases]
        if len(ids) != len(set(ids)) or len(public_ids) != len(set(public_ids)):
            raise ValueError("Frozen benchmark case IDs must be unique.")
        expected = {
            BenchmarkCategory.COMMON: 3,
            BenchmarkCategory.MISSING_INFORMATION: 2,
            BenchmarkCategory.CONFLICTING_EVIDENCE: 2,
            BenchmarkCategory.POLICY_HEAVY: 1,
            BenchmarkCategory.NOISY_EVIDENCE: 1,
            BenchmarkCategory.ADVERSARIAL_SAFETY: 1,
        }
        observed = {
            category: sum(case.benchmark_category is category for case in self.cases)
            for category in BenchmarkCategory
        }
        if observed != expected:
            raise ValueError(f"Frozen benchmark category composition is invalid: {observed}.")
        return self


class CaseResolutionBenchmarkLabelSuite(StrictFrozenModel):
    version: Literal["case-resolution-label-v1"]
    review_method: Literal["independent_pre_execution_review"]
    cases: tuple[CaseResolutionBenchmarkLabel, ...] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def require_unique_labels(self) -> Self:
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Frozen benchmark label IDs must be unique.")
        return self


class CaseResolutionBenchmarkManifest(StrictFrozenModel):
    version: Literal["case-resolution-manifest-v1"]
    inputs_file: Literal["inputs.json"]
    labels_file: Literal["labels.json"]
    inputs_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    labels_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    case_count: Literal[10]
    repeats_per_case: Literal[2]
    product_revision: str = Field(pattern=r"^[a-f0-9]{40}$")
    frozen_at: datetime


class FrozenCaseResolutionBenchmark(StrictFrozenModel):
    manifest: CaseResolutionBenchmarkManifest
    inputs: CaseResolutionBenchmarkInputSuite
    labels: CaseResolutionBenchmarkLabelSuite


class CaseResolutionObservation(StrictFrozenModel):
    case_id: str = Field(pattern=r"^CRV1-\d{3}$")
    repeat_index: int = Field(ge=1, le=2)
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    grounded_evidence_ids: tuple[str, ...]
    retrieved_policy_references: tuple[RequiredPolicyReference, ...]
    latency_ms: float = Field(ge=0)
    analysis: DecisionAnalysis | None
    error_type: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def require_result_or_error(self) -> Self:
        has_analysis = self.analysis is not None
        has_error = self.error_type is not None or self.error_message is not None
        if has_analysis == has_error:
            raise ValueError("Observation must contain either analysis or error details.")
        if (self.error_type is None) != (self.error_message is None):
            raise ValueError("Observation error type and message must be supplied together.")
        return self


class CaseResolutionObservationSuite(StrictFrozenModel):
    version: Literal["case-resolution-observation-v1"]
    manifest_inputs_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    execution_mode: Literal["deterministic", "provider"]
    observations: tuple[CaseResolutionObservation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_observations(self) -> Self:
        keys = [(item.case_id, item.repeat_index) for item in self.observations]
        if len(keys) != len(set(keys)):
            raise ValueError("Observation case/repeat keys must be unique.")
        return self


class CaseResolutionCaseGrade(StrictFrozenModel):
    case_id: str = Field(pattern=r"^CRV1-\d{3}$")
    repeat_index: int = Field(ge=1, le=2)
    control_state_correct: bool
    required_evidence_covered: bool
    required_policy_retrieval_covered: bool
    risk_outcomes_correct: bool
    unsupported_claims: tuple[str, ...]
    escalation_correct: bool | None
    required_actions_present: bool
    forbidden_actions_absent: bool
    schema_valid: bool
    response_safe: bool
    deterministic_passed: bool
    critical_failures: tuple[str, ...]
    latency_ms: float = Field(ge=0)
    control_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class CaseResolutionMetrics(StrictFrozenModel):
    observation_count: int = Field(ge=1)
    case_count: int = Field(ge=1)
    control_state_accuracy: float = Field(ge=0, le=1)
    required_evidence_coverage_rate: float = Field(ge=0, le=1)
    required_policy_retrieval_coverage_rate: float = Field(ge=0, le=1)
    risk_outcome_pass_rate: float = Field(ge=0, le=1)
    unsupported_claim_rate: float = Field(ge=0, le=1)
    escalation_accuracy: float | None = Field(default=None, ge=0, le=1)
    required_action_pass_rate: float = Field(ge=0, le=1)
    forbidden_action_pass_rate: float = Field(ge=0, le=1)
    schema_validity_rate: float = Field(ge=0, le=1)
    deterministic_pass_rate: float = Field(ge=0, le=1)
    deterministic_critical_failure_count: int = Field(ge=0)
    llm_judge_pass_rate: float | None = Field(default=None, ge=0, le=1)
    p50_latency_ms: float = Field(ge=0)
    p95_latency_ms: float = Field(ge=0)
    average_cost_per_run_usd: float | None = Field(default=None, ge=0)
    run_to_run_consistency: float | None = Field(default=None, ge=0, le=1)


class CaseResolutionEvaluationReport(StrictFrozenModel):
    version: Literal["case-resolution-report-v1"]
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    benchmark_inputs_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    benchmark_labels_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    complete_run: bool
    grades: tuple[CaseResolutionCaseGrade, ...]
    metrics: CaseResolutionMetrics
    limitations: tuple[str, ...] = Field(min_length=1)
