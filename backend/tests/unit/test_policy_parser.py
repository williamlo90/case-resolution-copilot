import pytest

from app.domain.policies import PolicyApplicability, PolicySourceParseError
from app.retrieval.policy_parser import parse_policy_source


def _applicability() -> PolicyApplicability:
    return PolicyApplicability(
        decision_scope="billing_adjustment",
        case_categories=["billing_dispute"],
        products=["all"],
        regions=["all"],
        channels=["all"],
        customer_tiers=["all"],
    )


def test_markdown_policy_parser_preserves_clause_boundaries() -> None:
    clauses = parse_policy_source(
        "## Eligibility\nA duplicate invoice must be verified before correction.\n\n"
        "## Authority\nA financial correction above authority requires supervisor review.",
        _applicability(),
    )

    assert [clause.heading for clause in clauses] == ["Eligibility", "Authority"]
    assert all("billing_adjustment" in clause.applies_when for clause in clauses)


def test_policy_parser_rejects_short_evidence() -> None:
    with pytest.raises(PolicySourceParseError, match="short"):
        parse_policy_source("Too short.", _applicability())
