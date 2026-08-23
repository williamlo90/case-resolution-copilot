from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.evaluation.retrieval_v2_contract import FrozenRetrievalBenchmark
from app.evaluation.retrieval_v2_runtime import run_retrieval_profile
from app.evaluation.retrieval_v2_scoring import (
    RetrievalProfileReport,
    score_retrieval_profile,
)
from app.persistence.database import Database
from app.retrieval.embeddings import DeterministicEmbeddingProvider, EmbeddingProvider
from app.retrieval.v2.embeddings import deterministic_policy_embedding_provider


class RetrievalV2BenchmarkReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["retrieval-v2-report-v1"] = "retrieval-v2-report-v1"
    generated_at: datetime
    inputs_sha256: str
    labels_sha256: str
    live_openai_evaluated: bool
    phase4_gate_passed: bool
    phase4_gate_failures: tuple[str, ...]
    profiles: tuple[RetrievalProfileReport, ...]


def run_frozen_retrieval_v2_benchmark(
    *,
    database: Database,
    benchmark: FrozenRetrievalBenchmark,
    openai_provider: EmbeddingProvider | None,
    query_character_limit: int,
) -> RetrievalV2BenchmarkReport:
    profile_runs: list[
        tuple[str, Literal["deterministic", "openai"], Literal["v1", "v2"], EmbeddingProvider]
    ] = [
        (
            "deterministic-hash-v1",
            "deterministic",
            "v1",
            DeterministicEmbeddingProvider(),
        ),
        (
            deterministic_policy_embedding_provider().version,
            "deterministic",
            "v2",
            deterministic_policy_embedding_provider(),
        ),
    ]
    if openai_provider is not None:
        profile_runs.append(
            (openai_provider.version, "openai", "v2", openai_provider)
        )

    reports: list[RetrievalProfileReport] = []
    for profile_key, provider_name, generation, provider in profile_runs:
        observations = run_retrieval_profile(
            database=database,
            inputs=benchmark.inputs,
            embedding_provider=provider,
            generation=generation,
            query_character_limit=query_character_limit,
        )
        reports.append(
            score_retrieval_profile(
                profile_key=profile_key,
                provider=provider_name,
                retrieval_generation=generation,
                labels=benchmark.labels,
                observations=observations,
            )
        )

    v2_reports = [report for report in reports if report.retrieval_generation == "v2"]
    failures = [
        f"{report.profile_key}:{failure}"
        for report in v2_reports
        for failure in report.metrics.gate_failures
    ]
    if openai_provider is None:
        failures.append("openai_profile:not_evaluated")
    return RetrievalV2BenchmarkReport(
        generated_at=datetime.now(UTC),
        inputs_sha256=benchmark.manifest.inputs_sha256,
        labels_sha256=benchmark.manifest.labels_sha256,
        live_openai_evaluated=openai_provider is not None,
        phase4_gate_passed=not failures,
        phase4_gate_failures=tuple(failures),
        profiles=tuple(reports),
    )
