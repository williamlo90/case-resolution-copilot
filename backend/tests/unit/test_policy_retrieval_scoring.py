from math import sqrt

import pytest

from app.retrieval.retriever import (
    RETRIEVAL_SCORE_THRESHOLD,
    _hybrid_relevance,
    _lexical_relevance,
)


def test_lexical_relevance_normalizes_punctuation_and_common_inflections() -> None:
    assert _lexical_relevance(
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

    duplicate_score = _hybrid_relevance(query, duplicate_charge, raw_distance=1.152944)
    approval_score = _hybrid_relevance(query, approval_threshold, raw_distance=0.777778)

    assert duplicate_score >= RETRIEVAL_SCORE_THRESHOLD
    assert duplicate_score > approval_score


def test_hybrid_relevance_preserves_vector_only_matches() -> None:
    assert _hybrid_relevance(
        "identity recovery",
        "unrelated vocabulary",
        raw_distance=0.7,
    ) == pytest.approx(0.3)
