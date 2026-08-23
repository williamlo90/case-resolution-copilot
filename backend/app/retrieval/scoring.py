import re
from math import sqrt

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "any",
        "are",
        "be",
        "been",
        "before",
        "being",
        "for",
        "i",
        "in",
        "is",
        "may",
        "my",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
    }
)
_TOKEN_ALIASES = {
    "charged": "charge",
    "charges": "charge",
    "charging": "charge",
    "credits": "credit",
    "duplicated": "duplicate",
    "duplicates": "duplicate",
}


def meaningful_terms(text: str) -> set[str]:
    return {
        _TOKEN_ALIASES.get(token, token)
        for token in _TOKEN_PATTERN.findall(text.lower())
        if token not in _STOP_WORDS
    }


def lexical_relevance(query: str, passage: str) -> float:
    query_terms = meaningful_terms(query)
    passage_terms = meaningful_terms(passage)
    if not query_terms or not passage_terms:
        return 0.0
    return len(query_terms & passage_terms) / sqrt(len(query_terms) * len(passage_terms))


def hybrid_relevance(query: str, passage: str, raw_distance: float) -> float:
    vector_relevance = min(1.0, max(0.0, 1.0 - float(raw_distance)))
    return max(vector_relevance, lexical_relevance(query, passage))
