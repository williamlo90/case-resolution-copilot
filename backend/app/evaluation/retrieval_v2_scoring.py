from __future__ import annotations

from math import ceil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.policies import EvidenceRetrievalStatus
from app.evaluation.retrieval_v2_contract import RetrievalBenchmarkLabelSuite


class RetrievedClauseObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_public_id: str
    policy_version: int = Field(ge=1)
    clause_public_id: str
    dense_rank: int | None = Field(default=None, ge=1)
    lexical_rank: int | None = Field(default=None, ge=1)
    score: float


class RetrievalCaseObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    status: EvidenceRetrievalStatus
    latency_ms: float = Field(ge=0)
    embedding_calls: int = Field(ge=0)
    boundary_outcome: Literal["organization_not_found"] | None = None
    clauses: tuple[RetrievedClauseObservation, ...] = ()


class RetrievalBenchmarkMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cases: int = Field(ge=1)
    relevant_cases: int = Field(ge=1)
    failure_state_cases: int = Field(ge=1)
    status_accuracy: float = Field(ge=0, le=1)
    policy_version_accuracy: float = Field(ge=0, le=1)
    safety_critical_policy_version_accuracy: float = Field(ge=0, le=1)
    recall_at_3: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)
    failure_state_accuracy: float = Field(ge=0, le=1)
    boundary_outcome_accuracy: float = Field(ge=0, le=1)
    wrong_version_count: int = Field(ge=0)
    unsupported_citation_count: int = Field(ge=0)
    cross_tenant_result_count: int = Field(ge=0)
    near_match_at_rank_1_count: int = Field(ge=0)
    embedding_calls: int = Field(ge=0)
    latency_p50_ms: float = Field(ge=0)
    latency_p95_ms: float = Field(ge=0)
    gate_passed: bool
    gate_failures: tuple[str, ...]


class RetrievalProfileReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_key: str
    provider: Literal["deterministic", "openai"]
    retrieval_generation: Literal["v1", "v2"]
    evidence_tier: Literal[
        "live_neon_release_corpus_plus_frozen_guard_contracts"
    ] = "live_neon_release_corpus_plus_frozen_guard_contracts"
    metrics: RetrievalBenchmarkMetrics
    observations: tuple[RetrievalCaseObservation, ...]


def score_retrieval_profile(
    *,
    profile_key: str,
    provider: Literal["deterministic", "openai"],
    retrieval_generation: Literal["v1", "v2"],
    labels: RetrievalBenchmarkLabelSuite,
    observations: tuple[RetrievalCaseObservation, ...],
) -> RetrievalProfileReport:
    by_id = {observation.case_id: observation for observation in observations}
    label_by_id = {label.case_id: label for label in labels.cases}
    if set(by_id) != set(label_by_id):
        raise ValueError(
            "Retrieval observation coverage mismatch; "
            f"missing={sorted(set(label_by_id) - set(by_id))}, "
            f"extra={sorted(set(by_id) - set(label_by_id))}."
        )

    relevant = [
        label
        for label in labels.cases
        if label.expected_status is EvidenceRetrievalStatus.RELEVANT
    ]
    failures = [
        label
        for label in labels.cases
        if label.expected_status is not EvidenceRetrievalStatus.RELEVANT
    ]
    safety = [label for label in relevant if label.safety_critical]
    boundary = [label for label in labels.cases if label.expected_boundary_outcome]

    status_hits = 0
    policy_version_hits = 0
    safety_hits = 0
    clause_hits = 0
    reciprocal_rank = 0.0
    failure_hits = 0
    boundary_hits = 0
    wrong_versions = 0
    unsupported = 0
    cross_tenant_results = 0
    near_match_rank_1 = 0

    for label in labels.cases:
        observation = by_id[label.case_id]
        status_hits += observation.status is label.expected_status
        unsupported += sum(
            clause.clause_public_id not in labels.corpus_clause_public_ids
            for clause in observation.clauses
        )
        if label.cross_tenant_probe:
            cross_tenant_results += len(observation.clauses)
        if label.expected_boundary_outcome:
            boundary_hits += observation.boundary_outcome == label.expected_boundary_outcome
        if label.expected_status is not EvidenceRetrievalStatus.RELEVANT:
            failure_hits += observation.status is label.expected_status
            continue

        expected_pair = (
            label.expected_policy_public_id,
            label.expected_policy_version,
        )
        pair_hit = any(
            (clause.policy_public_id, clause.policy_version) == expected_pair
            for clause in observation.clauses[:3]
        )
        policy_version_hits += pair_hit
        if label.safety_critical:
            safety_hits += pair_hit
        wrong_versions += sum(
            clause.policy_public_id == label.expected_policy_public_id
            and clause.policy_version != label.expected_policy_version
            for clause in observation.clauses
        )
        ranks = [
            rank
            for rank, clause in enumerate(observation.clauses[:3], start=1)
            if clause.clause_public_id == label.expected_clause_public_id
        ]
        if ranks:
            clause_hits += 1
            reciprocal_rank += 1 / ranks[0]
        if (
            observation.clauses
            and label.near_match_clause_public_id
            and observation.clauses[0].clause_public_id
            == label.near_match_clause_public_id
        ):
            near_match_rank_1 += 1

    status_accuracy = status_hits / len(labels.cases)
    policy_version_accuracy = policy_version_hits / len(relevant)
    safety_accuracy = safety_hits / len(safety) if safety else 1.0
    recall_at_3 = clause_hits / len(relevant)
    mrr = reciprocal_rank / len(relevant)
    failure_accuracy = failure_hits / len(failures)
    boundary_accuracy = boundary_hits / len(boundary) if boundary else 1.0

    gates = {
        "safety_critical_policy_version_accuracy": safety_accuracy == 1.0,
        "cross_tenant_results": cross_tenant_results == 0,
        "unsupported_citations": unsupported == 0,
        "wrong_active_version": wrong_versions == 0,
        "failure_state_classification": failure_accuracy == 1.0,
        "boundary_outcome": boundary_accuracy == 1.0,
        "recall_at_3": recall_at_3 >= 0.90,
    }
    gate_failures = tuple(name for name, passed in gates.items() if not passed)
    latencies = sorted(observation.latency_ms for observation in observations)
    metrics = RetrievalBenchmarkMetrics(
        cases=len(labels.cases),
        relevant_cases=len(relevant),
        failure_state_cases=len(failures),
        status_accuracy=status_accuracy,
        policy_version_accuracy=policy_version_accuracy,
        safety_critical_policy_version_accuracy=safety_accuracy,
        recall_at_3=recall_at_3,
        mean_reciprocal_rank=mrr,
        failure_state_accuracy=failure_accuracy,
        boundary_outcome_accuracy=boundary_accuracy,
        wrong_version_count=wrong_versions,
        unsupported_citation_count=unsupported,
        cross_tenant_result_count=cross_tenant_results,
        near_match_at_rank_1_count=near_match_rank_1,
        embedding_calls=sum(item.embedding_calls for item in observations),
        latency_p50_ms=_nearest_rank(latencies, 0.50),
        latency_p95_ms=_nearest_rank(latencies, 0.95),
        gate_passed=not gate_failures,
        gate_failures=gate_failures,
    )
    return RetrievalProfileReport(
        profile_key=profile_key,
        provider=provider,
        retrieval_generation=retrieval_generation,
        metrics=metrics,
        observations=observations,
    )


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = max(0, ceil(percentile * len(values)) - 1)
    return values[index]
