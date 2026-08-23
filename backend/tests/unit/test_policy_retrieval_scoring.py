from math import sqrt

import pytest

from app.retrieval.retriever import RETRIEVAL_SCORE_THRESHOLD
from app.retrieval.scoring import hybrid_relevance, lexical_relevance


def test_lexical_relevance_normalizes_punctuation_and_common_inflections() -> None:
    assert lexical_relevance(
        "I was charged for the support plan.",
        "A duplicate support plan charge was verified.",
    ) == pytest.approx(3 / sqrt(15))


def test_hybrid_relevance_corrects_a_vector_collision_for_duplicate_charge() -> None:
    query = "I was charged twice for my enterprise support plan."
    duplicate_charge = (
        "A verified duplicate support plan charge may receive a service credit "
        "after invoice and account ownership checks."
    )
    approval_threshold = (
        "Credits above the agent authority threshold require supervisor approval "
        "before any account change is executed."
    )

    duplicate_score = hybrid_relevance(query, duplicate_charge, raw_distance=1.152944)
    approval_score = hybrid_relevance(query, approval_threshold, raw_distance=0.777778)

    assert duplicate_score >= RETRIEVAL_SCORE_THRESHOLD
    assert duplicate_score > approval_score


def test_hybrid_relevance_preserves_vector_only_matches() -> None:
    assert hybrid_relevance(
        "identity recovery",
        "unrelated vocabulary",
        raw_distance=0.7,
    ) == pytest.approx(0.3)


def test_governed_lexical_fallback_recognizes_prefixed_duplicate_charge_subject() -> None:
    query = (
        "[CRC-PILOT-001] Duplicate charge after plan upgrade "
        "[CRC-PILOT-001] Duplicate charge after plan upgrade"
    )
    policy_clause = (
        "A verified duplicate invoice charge may be reversed or credited after the invoice "
        "and payment references are confirmed."
    )

    assert lexical_relevance(query, policy_clause) >= RETRIEVAL_SCORE_THRESHOLD
