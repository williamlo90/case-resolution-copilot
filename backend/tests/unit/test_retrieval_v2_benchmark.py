from pathlib import Path

import pytest

from app.domain.policies import EvidenceRetrievalStatus
from app.evaluation.retrieval_v2_contract import load_frozen_retrieval_benchmark
from app.evaluation.retrieval_v2_scoring import (
    RetrievalCaseObservation,
    RetrievedClauseObservation,
    score_retrieval_profile,
)


def _benchmark_root() -> Path:
    return Path(__file__).resolve().parents[2] / "evaluations" / "retrieval_v2"


def test_frozen_retrieval_v2_dataset_is_hash_locked_and_answer_separated() -> None:
    benchmark = load_frozen_retrieval_benchmark(_benchmark_root())

    assert len(benchmark.inputs.cases) == 15
    assert len(benchmark.labels.cases) == 15
    assert len(benchmark.labels.corpus_clause_public_ids) == 8
    assert sum(case.lane == "release_corpus" for case in benchmark.inputs.cases) == 10
    assert sum(case.lane == "guard_contract" for case in benchmark.inputs.cases) == 5
    input_payload = (_benchmark_root() / "inputs.json").read_text(encoding="utf-8")
    assert "expected_status" not in input_payload
    assert "expected_clause_public_id" not in input_payload


def test_frozen_retrieval_v2_loader_rejects_dataset_drift(tmp_path: Path) -> None:
    root = _benchmark_root()
    for name in ("manifest.json", "inputs.json", "labels.json"):
        (tmp_path / name).write_bytes((root / name).read_bytes())
    (tmp_path / "inputs.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="inputs hash mismatch"):
        load_frozen_retrieval_benchmark(tmp_path)


def test_perfect_retrieval_observations_pass_the_phase4_profile_gate() -> None:
    benchmark = load_frozen_retrieval_benchmark(_benchmark_root())
    observations = []
    for label in benchmark.labels.cases:
        clauses: tuple[RetrievedClauseObservation, ...] = ()
        if label.expected_status is EvidenceRetrievalStatus.RELEVANT:
            assert label.expected_policy_public_id is not None
            assert label.expected_policy_version is not None
            assert label.expected_clause_public_id is not None
            clauses = (
                RetrievedClauseObservation(
                    policy_public_id=label.expected_policy_public_id,
                    policy_version=label.expected_policy_version,
                    clause_public_id=label.expected_clause_public_id,
                    dense_rank=1,
                    lexical_rank=1,
                    score=1.0,
                ),
            )
        observations.append(
            RetrievalCaseObservation(
                case_id=label.case_id,
                status=label.expected_status,
                latency_ms=1.0,
                embedding_calls=1 if clauses else 0,
                boundary_outcome=label.expected_boundary_outcome,
                clauses=clauses,
            )
        )

    report = score_retrieval_profile(
        profile_key="deterministic-hash-v2-d512",
        provider="deterministic",
        retrieval_generation="v2",
        labels=benchmark.labels,
        observations=tuple(observations),
    )

    assert report.metrics.gate_passed
    assert report.metrics.recall_at_3 == 1.0
    assert report.metrics.failure_state_accuracy == 1.0
    assert report.metrics.unsupported_citation_count == 0
