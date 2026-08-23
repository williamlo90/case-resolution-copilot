import re

_COMPLETED_ACTION_CLAIMS = (
    re.compile(
        r"\b(?:we(?:'ve)?|i(?:'ve)?|our team|the system)\s+"
        r"(?:(?:have|has|did)\s+)?(?:already\s+)?"
        r"(?:approved|completed|executed|issued|processed|sent|applied|"
        r"refunded|credited|reversed|cancelled|canceled)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:your\s+|the\s+)?(?:refund|credit|account change|action|"
        r"cancellation|reversal|email|reply)\s+"
        r"(?:has|have|is|are|was|were)\s+"
        r"(?:(?:already|now)\s+)?(?:been\s+)?"
        r"(?:approved|completed|executed|issued|processed|sent|applied|"
        r"refunded|credited|reversed|cancelled|canceled|complete)\b",
        re.IGNORECASE,
    ),
)


def contains_completed_action_claim(*texts: str) -> bool:
    """Return whether generated language claims a controlled action already happened."""

    combined = " ".join(texts)
    return any(pattern.search(combined) for pattern in _COMPLETED_ACTION_CLAIMS)
