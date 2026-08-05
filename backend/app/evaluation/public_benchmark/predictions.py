from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, field_validator

from app.evaluation.public_benchmark.models import (
    FosOutcome,
    RecordId,
    Sha256,
    SuiteName,
)

CfpbResponse = Literal[
    "Closed with explanation",
    "Closed with monetary relief",
    "Closed with non-monetary relief",
]
UciRelationship = Literal["candidate_cancellation_match", "unrelated_pair"]
RunId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")]
RUN_ID_ADAPTER: TypeAdapter[RunId] = TypeAdapter(RunId)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CfpbPredictionPayload(StrictModel):
    company_response: CfpbResponse
    timely_response: bool
    rationale_signals: list[str] = Field(default_factory=list, max_length=12)


class FosPredictionPayload(StrictModel):
    outcome: FosOutcome
    rationale_signals: list[str] = Field(default_factory=list, max_length=12)


class UciPredictionPayload(StrictModel):
    relationship: UciRelationship
    expected_original_invoice: str | None = None
    rationale_signals: list[str] = Field(default_factory=list, max_length=12)


class PredictionRecordBase(StrictModel):
    schema_version: Literal["public-benchmark-prediction-v1"] = "public-benchmark-prediction-v1"
    suite: SuiteName
    record_id: RecordId
    input_sha256: Sha256
    predictor: str = Field(min_length=1, max_length=100)
    predictor_version: str = Field(min_length=1, max_length=100)


class CfpbPredictionRecord(PredictionRecordBase):
    suite: Literal["cfpb"] = "cfpb"
    payload: CfpbPredictionPayload


class FosPredictionRecord(PredictionRecordBase):
    suite: Literal["fos"] = "fos"
    payload: FosPredictionPayload


class UciPredictionRecord(PredictionRecordBase):
    suite: Literal["uci"] = "uci"
    payload: UciPredictionPayload


BenchmarkPredictionRecord = Annotated[
    CfpbPredictionRecord | FosPredictionRecord | UciPredictionRecord,
    Field(discriminator="suite"),
]
BENCHMARK_PREDICTION_ADAPTER: TypeAdapter[BenchmarkPredictionRecord] = TypeAdapter(
    BenchmarkPredictionRecord
)


class RunArtifact(StrictModel):
    path: str = Field(min_length=1)
    sha256: Sha256
    bytes: int = Field(ge=0)
    records: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def require_safe_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
            raise ValueError("Benchmark run artifact paths must be safe relative paths.")
        return normalized


class InputSnapshot(RunArtifact):
    suite: SuiteName


class PredictionRunManifest(StrictModel):
    schema_version: Literal["public-benchmark-run-v1"] = "public-benchmark-run-v1"
    run_id: RunId
    generated_at: datetime
    predictor: str = Field(min_length=1, max_length=100)
    predictor_version: str = Field(min_length=1, max_length=100)
    source_manifest_sha256: Sha256
    input_snapshots: list[InputSnapshot] = Field(min_length=3, max_length=3)
    predictions: RunArtifact
    phase_contract: Literal["inputs_only"] = "inputs_only"


class SuiteMetrics(StrictModel):
    suite: SuiteName
    task: str = Field(min_length=1, max_length=200)
    records: int = Field(ge=1)
    accuracy: float = Field(ge=0, le=1)
    macro_f1: float = Field(ge=0, le=1)
    expected_distribution: dict[str, int]
    predicted_distribution: dict[str, int]
    confusion_matrix: dict[str, dict[str, int]]
    secondary_metrics: dict[str, float]
    interpretation: str = Field(min_length=1, max_length=1000)


class PublicBenchmarkReport(StrictModel):
    schema_version: Literal["public-benchmark-report-v1"] = "public-benchmark-report-v1"
    run_id: RunId
    scored_at: datetime
    evaluator: Literal["public-benchmark-scorer-v1"] = "public-benchmark-scorer-v1"
    predictor: str
    predictor_version: str
    source_manifest_sha256: Sha256
    prediction_manifest_sha256: Sha256
    label_snapshots: list[InputSnapshot] = Field(min_length=3, max_length=3)
    suites: list[SuiteMetrics] = Field(min_length=3, max_length=3)
    integrity_checks: list[str] = Field(min_length=1)
    permitted_claim: str = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
