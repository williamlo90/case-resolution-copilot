from pathlib import Path

from app.evaluation.retrieval import run_retrieval_benchmark
from app.persistence.database import Database


def test_versioned_retrieval_benchmark_meets_initial_gate(database: Database) -> None:
    dataset = Path(__file__).resolve().parents[2] / "evaluations" / "retrieval" / "golden.json"
    metrics = run_retrieval_benchmark(database, dataset)

    assert metrics.cases == 7
    assert metrics.decision_accuracy == 1.0
    assert metrics.recall_at_3 == 1.0
    assert metrics.mrr >= 0.75
