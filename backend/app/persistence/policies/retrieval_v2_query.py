import re

LEXICAL_QUERY_TERM_LIMIT = 24
_TOKEN = re.compile(r"[a-z0-9]{3,}")
_STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "appears",
        "before",
        "because",
        "case",
        "check",
        "confirm",
        "customer",
        "from",
        "have",
        "into",
        "must",
        "policy",
        "request",
        "same",
        "support",
        "that",
        "their",
        "this",
        "with",
    }
)


def lexical_websearch_query(text: str) -> str:
    """Build a bounded OR query so long case summaries do not become an all-term filter."""

    terms: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN.findall(text.lower()):
        if token in _STOP_WORDS or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) == LEXICAL_QUERY_TERM_LIMIT:
            break
    return " OR ".join(terms) or "unmatched"
