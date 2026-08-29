from __future__ import annotations

from math import ceil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.policies import EvidenceRetrievalStatus
from app.evaluation.wave1_rag_contract import Wave1RagFixture


class Wave1RagCaseObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    expected_status: EvidenceRetrievalStatus
    observed_status: EvidenceRetrievalStatus | None
    expected_source_ids: tuple[str, ...]
    retrieved_source_ids: tuple[str, ...]
    latency_ms: float = Field(ge=0)
    error_code: str | None = None


class Wave1RagMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cases: int = Field(ge=1)
    runtime_failure_count: int = Field(ge=0)
    status_accuracy: float = Field(ge=0, le=1)
    source_hit_rate_at_3: float = Field(ge=0, le=1)
    source_recall_at_3: float = Field(ge=0, le=1)
    latency_p50_ms: float = Field(ge=0)
    latency_p95_ms: float = Field(ge=0)
    gate_passed: bool
    gate_failures: tuple[str, ...]


class Wave1RagReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["wave1-rag-report-v1"] = "wave1-rag-report-v1"
    fixture_version: str
    credential_free: Literal[True] = True
    retrieval_implementation: Literal["governed_v2_in_memory_adapter"] = (
        "governed_v2_in_memory_adapter"
    )
    metrics: Wave1RagMetrics
    observations: tuple[Wave1RagCaseObservation, ...]


def score_wave1_rag(
    *,
    fixture: Wave1RagFixture,
    observations: tuple[Wave1RagCaseObservation, ...],
) -> Wave1RagReport:
    expected_ids = {case.id for case in fixture.cases}
    observed_ids = {observation.case_id for observation in observations}
    if expected_ids != observed_ids or len(observations) != len(observed_ids):
        raise ValueError(
            "Wave 1 RAG observation coverage mismatch; "
            f"missing={sorted(expected_ids - observed_ids)}, "
            f"extra={sorted(observed_ids - expected_ids)}."
        )

    relevant = [item for item in observations if item.expected_source_ids]
    runtime_failures = [item for item in observations if item.error_code]
    status_hits = sum(item.observed_status is item.expected_status for item in observations)
    source_hits = 0
    expected_sources = 0
    retrieved_expected_sources = 0
    case_failures: list[str] = []
    for item in observations:
        if item.error_code:
            case_failures.append(f"{item.case_id}:runtime:{item.error_code}")
        if item.observed_status is not item.expected_status:
            observed = item.observed_status.value if item.observed_status else "runtime_failure"
            case_failures.append(
                f"{item.case_id}:status:expected_{item.expected_status.value}:observed_{observed}"
            )
        expected = set(item.expected_source_ids)
        retrieved = set(item.retrieved_source_ids[:3])
        if expected:
            hits = expected & retrieved
            source_hits += bool(hits)
            expected_sources += len(expected)
            retrieved_expected_sources += len(hits)
            if hits != expected:
                case_failures.append(f"{item.case_id}:expected_source_not_retrieved")

    status_accuracy = status_hits / len(observations)
    hit_rate = source_hits / len(relevant) if relevant else 1.0
    recall = retrieved_expected_sources / expected_sources if expected_sources else 1.0
    latencies = sorted(item.latency_ms for item in observations)
    aggregate_failures = []
    if runtime_failures:
        aggregate_failures.append("runtime_failures")
    if status_accuracy < 1.0:
        aggregate_failures.append("status_accuracy")
    if hit_rate < 1.0:
        aggregate_failures.append("source_hit_rate_at_3")
    if recall < 1.0:
        aggregate_failures.append("source_recall_at_3")
    gate_failures = tuple(dict.fromkeys([*aggregate_failures, *case_failures]))
    return Wave1RagReport(
        fixture_version=fixture.version,
        metrics=Wave1RagMetrics(
            cases=len(observations),
            runtime_failure_count=len(runtime_failures),
            status_accuracy=status_accuracy,
            source_hit_rate_at_3=hit_rate,
            source_recall_at_3=recall,
            latency_p50_ms=_nearest_rank(latencies, 0.50),
            latency_p95_ms=_nearest_rank(latencies, 0.95),
            gate_passed=not gate_failures,
            gate_failures=gate_failures,
        ),
        observations=observations,
    )


def _nearest_rank(values: list[float], percentile: float) -> float:
    index = max(0, ceil(percentile * len(values)) - 1)
    return values[index]
