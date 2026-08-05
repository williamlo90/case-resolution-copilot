from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter

from app.evaluation.public_benchmark.ai_predictor import (
    ModelConfidence,
    ProviderErrorCategory,
)
from app.evaluation.public_benchmark.models import RecordId, Sha256, SuiteName
from app.evaluation.public_benchmark.predictions import InputSnapshot, RunArtifact, RunId

AI_RUN_ID_ADAPTER: TypeAdapter[RunId] = TypeAdapter(RunId)
AiDecision = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AITextPredictionMetadata(StrictModel):
    confidence: ModelConfidence
    evidence_quotes: list[str] = Field(default_factory=list, max_length=4)
    unsupported_evidence_quotes: list[str] = Field(default_factory=list, max_length=4)
    uncertainty: str = Field(min_length=1, max_length=500)
    schema_valid: bool
    review_required: bool
    action_status: Literal["analysis_only"]
    provider_error_category: ProviderErrorCategory | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class AICfpbPredictionPayload(AITextPredictionMetadata):
    company_response: Literal[
        "Closed with explanation",
        "Closed with monetary relief",
        "Closed with non-monetary relief",
        "abstain",
    ]


class AIFosPredictionPayload(AITextPredictionMetadata):
    outcome: Literal["upheld", "partially_upheld", "not_upheld", "abstain"]


class AIUciPredictionPayload(StrictModel):
    relationship: Literal["candidate_cancellation_match", "unrelated_pair"]
    expected_original_invoice: str | None = None
    rationale_signals: list[str] = Field(default_factory=list, max_length=12)


class AIPredictionRecordBase(StrictModel):
    schema_version: Literal["public-ai-benchmark-prediction-v1"] = (
        "public-ai-benchmark-prediction-v1"
    )
    suite: SuiteName
    record_id: RecordId
    input_sha256: Sha256
    predictor: str = Field(min_length=1, max_length=100)
    predictor_version: str = Field(min_length=1, max_length=100)
    prompt_sha256: Sha256
    execution_mode: Literal["model", "deterministic"]


class AICfpbPredictionRecord(AIPredictionRecordBase):
    suite: Literal["cfpb"] = "cfpb"
    execution_mode: Literal["model"] = "model"
    payload: AICfpbPredictionPayload


class AIFosPredictionRecord(AIPredictionRecordBase):
    suite: Literal["fos"] = "fos"
    execution_mode: Literal["model"] = "model"
    payload: AIFosPredictionPayload


class AIUciPredictionRecord(AIPredictionRecordBase):
    suite: Literal["uci"] = "uci"
    execution_mode: Literal["deterministic"] = "deterministic"
    payload: AIUciPredictionPayload


AIPredictionRecord = Annotated[
    AICfpbPredictionRecord | AIFosPredictionRecord | AIUciPredictionRecord,
    Field(discriminator="suite"),
]
AI_PREDICTION_ADAPTER: TypeAdapter[AIPredictionRecord] = TypeAdapter(AIPredictionRecord)


class AIEvaluationContract(StrictModel):
    schema_version: Literal["public-ai-benchmark-contract-v1"] = (
        "public-ai-benchmark-contract-v1"
    )
    run_id: RunId
    frozen_at: datetime
    predictor: Literal["openai-public-evidence-evaluator"] = (
        "openai-public-evidence-evaluator"
    )
    predictor_version: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)
    prompt_sha256: Sha256
    source_manifest_sha256: Sha256
    input_snapshots: list[InputSnapshot] = Field(min_length=3, max_length=3)
    task_order: list[Literal["fos", "cfpb"]] = Field(min_length=2, max_length=2)
    model_call_budget: int = Field(ge=1, le=46)
    max_output_tokens: int = Field(ge=100, le=1200)
    timeout_seconds: float = Field(ge=1, le=60)
    max_retries: Literal[0] = 0
    serial_execution: Literal[True] = True
    phase_contract: Literal["inputs_only"] = "inputs_only"


class AIPredictionProgress(StrictModel):
    schema_version: Literal["public-ai-benchmark-progress-v1"] = (
        "public-ai-benchmark-progress-v1"
    )
    run_id: RunId
    contract_sha256: Sha256
    updated_at: datetime
    calls_started: int = Field(ge=0, le=46)
    completed_record_ids: list[RecordId]
    active_record_id: RecordId | None = None
    provider_errors: dict[ProviderErrorCategory, int] = Field(default_factory=dict)


class AIPredictionManifest(StrictModel):
    schema_version: Literal["public-ai-benchmark-run-v1"] = "public-ai-benchmark-run-v1"
    run_id: RunId
    completed_at: datetime
    predictor: str
    predictor_version: str
    model: str
    prompt_sha256: Sha256
    contract_sha256: Sha256
    source_manifest_sha256: Sha256
    input_snapshots: list[InputSnapshot] = Field(min_length=3, max_length=3)
    predictions: RunArtifact
    model_calls_started: int = Field(ge=0, le=46)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    phase_contract: Literal["inputs_only"] = "inputs_only"


class AISuiteMetrics(StrictModel):
    suite: SuiteName
    task: str = Field(min_length=1, max_length=240)
    records: int = Field(ge=1)
    accuracy: float = Field(ge=0, le=1)
    macro_f1: float = Field(ge=0, le=1)
    abstention_rate: float = Field(ge=0, le=1)
    schema_validity_rate: float = Field(ge=0, le=1)
    unsupported_evidence_quote_rate: float = Field(ge=0, le=1)
    expected_distribution: dict[str, int]
    predicted_distribution: dict[str, int]
    confusion_matrix: dict[str, dict[str, int]]
    secondary_metrics: dict[str, float]
    interpretation: str = Field(min_length=1, max_length=1200)


class AISafetyMetrics(StrictModel):
    model_records: int = Field(ge=1)
    approval_boundary_preservation_rate: float = Field(ge=0, le=1)
    unsafe_action_rate: float = Field(ge=0, le=1)
    enforcement: Literal["structured_output_and_server_validation"] = (
        "structured_output_and_server_validation"
    )


class AIUsageSummary(StrictModel):
    model_calls_started: int = Field(ge=0, le=46)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class AIPublicBenchmarkReport(StrictModel):
    schema_version: Literal["public-ai-benchmark-report-v1"] = (
        "public-ai-benchmark-report-v1"
    )
    run_id: RunId
    scored_at: datetime
    evaluator: Literal["public-ai-benchmark-scorer-v1"] = (
        "public-ai-benchmark-scorer-v1"
    )
    predictor: str
    predictor_version: str
    model: str
    prompt_sha256: Sha256
    contract_sha256: Sha256
    prediction_manifest_sha256: Sha256
    label_snapshots: list[InputSnapshot] = Field(min_length=3, max_length=3)
    suites: list[AISuiteMetrics] = Field(min_length=3, max_length=3)
    safety: AISafetyMetrics
    usage: AIUsageSummary
    integrity_checks: list[str] = Field(min_length=1)
    permitted_claim: str = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)


ContractHash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
