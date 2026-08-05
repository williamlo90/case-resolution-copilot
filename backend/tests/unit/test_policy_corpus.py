import json
from pathlib import Path

from app.retrieval.ingest import CORPUS_VERSION, PolicySource

ROOT = Path(__file__).resolve().parents[2]


def test_support_policy_corpus_is_versioned_and_covers_core_case_categories() -> None:
    sources = [
        PolicySource.model_validate(json.loads(path.read_text()))
        for path in sorted((ROOT / "policies" / "source").glob("*.json"))
    ]

    assert CORPUS_VERSION == "support-policy-corpus-v1"
    assert len(sources) == 6
    assert len({(source.source_id, source.version) for source in sources}) == 6
    assert {source.case_category for source in sources} == {
        "account_access",
        "billing",
        "cancellation",
        "privacy",
        "service_complaint",
        "sla_breach",
    }
    assert all(source.clauses for source in sources)


def test_retrieval_benchmark_covers_safe_abstention_states() -> None:
    cases = json.loads((ROOT / "evaluations" / "retrieval" / "golden.json").read_text())

    assert {case["expected_status"] for case in cases} == {
        "relevant",
        "missing",
        "stale",
        "inapplicable",
        "conflicting",
    }
    assert all("as_of" in case and "customer_tier" in case for case in cases)
