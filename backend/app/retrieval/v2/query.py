import re
from hashlib import sha256

from app.domain.retrieval_v2 import MinimizedPolicyQuery

_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")
_PAYMENT = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_WHITESPACE = re.compile(r"\s+")


def build_policy_query(
    *,
    category: str,
    issue: str,
    request_summary: str,
    products: set[str],
    requested_remedy: str | None = None,
    problem_terms: tuple[str, ...] = (),
    max_characters: int = 2000,
) -> MinimizedPolicyQuery:
    if max_characters < 200 or max_characters > 4000:
        raise ValueError("Policy query limit must be between 200 and 4000 characters.")
    parts = [
        f"category: {_clean(category)}",
        f"issue: {_clean(issue)}",
        f"request: {_clean(request_summary)}",
        f"products: {', '.join(sorted(_clean(item) for item in products))}",
    ]
    if requested_remedy:
        parts.append(f"requested remedy: {_clean(requested_remedy)}")
    if problem_terms:
        parts.append(
            "problem terms: " + ", ".join(dict.fromkeys(_clean(item) for item in problem_terms))
        )
    text = "\n".join(part for part in parts if not part.endswith(": "))[:max_characters]
    if not text.strip():
        raise ValueError("Policy query material is empty.")
    return MinimizedPolicyQuery(
        text=text,
        fingerprint=sha256(text.encode("utf-8")).hexdigest(),
        omitted_fields=("raw_conversation", "contact_details", "payment_details"),
    )


def _clean(value: str) -> str:
    without_identifiers = _PAYMENT.sub(" ", _PHONE.sub(" ", _EMAIL.sub(" ", value)))
    return _WHITESPACE.sub(" ", without_identifiers).strip()[:1000]
