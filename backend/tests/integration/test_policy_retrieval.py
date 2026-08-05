from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.persistence.database import Database
from app.persistence.models import PolicyDocumentVersionModel
from app.retrieval.ingest import ingest_policy
from app.retrieval.retriever import PolicyRetriever

SOURCE = Path(__file__).resolve().parents[2] / "policies" / "source" / "billing-credit-v1.json"


def test_ingestion_is_idempotent_and_published_version_is_immutable(
    database: Database, tmp_path: Path
) -> None:
    ingest_policy(database, SOURCE)
    with database.session() as session:
        assert session.scalar(select(func.count()).select_from(PolicyDocumentVersionModel)) == 6

    changed = tmp_path / "changed.json"
    changed.write_text(SOURCE.read_text().replace("service credit", "cash refund"))
    with pytest.raises(ValueError, match="cannot be replaced"):
        ingest_policy(database, changed)


@pytest.mark.parametrize(
    ("category", "plan", "jurisdiction", "tier", "as_of", "expected"),
    [
        ("billing", "enterprise", "SG", "vip", date(2026, 7, 12), "relevant"),
        ("hardware", "enterprise", "SG", "standard", date(2026, 7, 12), "missing"),
        ("billing", "enterprise", "SG", "standard", date(2025, 12, 1), "stale"),
        ("privacy", "enterprise", "US", "standard", date(2026, 7, 12), "inapplicable"),
        ("service_complaint", "enterprise", "SG", "standard", date(2026, 7, 12), "inapplicable"),
    ],
)
def test_retrieval_decision_explains_unsafe_evidence_gaps(
    database: Database,
    category: str,
    plan: str,
    jurisdiction: str,
    tier: str,
    as_of: date,
    expected: str,
) -> None:
    decision = PolicyRetriever(database).decide(
        query="duplicate charge privacy priority support",
        case_category=category,
        plan=plan,
        jurisdiction=jurisdiction,
        customer_tier=tier,
        as_of=as_of,
    )
    assert decision.status == expected


def test_conflicting_active_documents_abstain(database: Database, tmp_path: Path) -> None:
    conflict = tmp_path / "conflict.json"
    conflict.write_text(
        SOURCE.read_text()
        .replace('"source_id": "SUP-BILLING-CREDIT"', '"source_id": "SUP-BILLING-CONFLICT"')
        .replace('"version": 1', '"version": 2')
    )
    ingest_policy(database, conflict)
    decision = PolicyRetriever(database).decide(
        query="duplicate support plan charge service credit",
        case_category="billing",
        plan="enterprise",
        jurisdiction="SG",
        customer_tier="vip",
        as_of=date(2026, 7, 12),
    )
    assert decision.status == "conflicting"

    assert PolicyRetriever(database).retrieve_and_bind(
        proposal_id=uuid4(),
        query="duplicate support plan charge service credit",
        case_category="billing",
        plan="enterprise",
        jurisdiction="SG",
        customer_tier="vip",
        as_of=date(2026, 7, 12),
    ) == []
