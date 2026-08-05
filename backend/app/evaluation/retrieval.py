import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.persistence.database import Database
from app.retrieval.ingest import ingest_policy
from app.retrieval.retriever import PolicyRetriever


@dataclass(frozen=True)
class RetrievalMetrics:
    cases: int
    decision_accuracy: float
    recall_at_3: float
    mrr: float


def run_retrieval_benchmark(database: Database, dataset: Path) -> RetrievalMetrics:
    cases: list[dict[str, str]] = json.loads(dataset.read_text())
    hits = 0
    correct_decisions = 0
    reciprocal_rank = 0.0
    retriever = PolicyRetriever(database)
    for case in cases:
        if setup_policy := case.get("setup_policy"):
            ingest_policy(database, dataset.parent / "fixtures" / setup_policy)
        decision = retriever.decide(
            query=case["query"],
            case_category=case["case_category"],
            plan=case["plan"],
            jurisdiction=case["jurisdiction"],
            customer_tier=case["customer_tier"],
            as_of=date.fromisoformat(case["as_of"]),
        )
        if decision.status == case["expected_status"]:
            correct_decisions += 1
        expected = case.get("relevant_clause")
        clauses = [row[0].clause for row in decision.matches]
        if expected and expected in clauses:
            rank = clauses.index(expected) + 1
            hits += 1
            reciprocal_rank += 1 / rank
    count = len(cases)
    relevant_count = sum(1 for case in cases if case["expected_status"] == "relevant")
    return RetrievalMetrics(
        cases=count,
        decision_accuracy=correct_decisions / count if count else 0.0,
        recall_at_3=hits / relevant_count if relevant_count else 0.0,
        mrr=reciprocal_rank / relevant_count if relevant_count else 0.0,
    )
