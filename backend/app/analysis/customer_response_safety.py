import re

from app.domain.decision_briefs import DecisionAnalysis, DecisionProposalState

_INTERNAL_CONTROL_LANGUAGE = re.compile(
    r"\b(?:POL|FCT|RSK|CTX|EVD|PRP)-[A-Z0-9-]+\b|"
    r"\b(?:low|medium|high)\s+confidence\b|"
    r"\b(?:supervisor|specialist|branch manager|administrator)\s+"
    r"(?:review|approval)\b|"
    r"\b(?:risk check|policy version)\b",
    re.IGNORECASE,
)

_REQUEST_LANGUAGE = re.compile(
    r"\b(?:please|send|provide|confirm|complete|share|need|needed|required)\b",
    re.IGNORECASE,
)

_REVIEW_LANGUAGE = re.compile(
    r"\b(?:pending|review|approval|approve|not\s+.+\s+yet|before\s+any)\b",
    re.IGNORECASE,
)


def customer_response_is_aligned(
    analysis: DecisionAnalysis,
    *,
    subject: str,
    body: str,
) -> bool:
    """Reject model wording that diverges from the governed next safe action."""

    combined = f"{subject} {body}"
    if _INTERNAL_CONTROL_LANGUAGE.search(combined):
        return False

    if analysis.state is DecisionProposalState.INFORMATION_NEEDED:
        blocking = [gap for gap in analysis.missing_information if gap.blocking]
        return bool(_REQUEST_LANGUAGE.search(body)) and any(
            _addresses_gap(gap.label, body) for gap in blocking
        )

    actions = analysis.proposed_actions
    if not actions:
        return False
    if not any(_addresses_action(action.type, body) for action in actions):
        return False
    if any(action.review_required for action in actions):
        return bool(_REVIEW_LANGUAGE.search(body))
    return True


def _addresses_gap(label: str, body: str) -> bool:
    text = body.lower()
    if label == "Second payment reference":
        return (
            _contains_any(text, "second", "another")
            and _contains_any(text, "payment", "charge", "transaction")
            and _contains_any(text, "reference", "statement", "settled", "evidence")
        )
    if label == "Service delivery status":
        return _contains_any(text, "service", "delivery") and _contains_any(
            text, "status", "started", "used"
        )
    if label == "Identity verification":
        return _contains_any(text, "identity", "ownership") and _contains_any(
            text, "verify", "verification", "check"
        )
    if label == "Service outcome":
        return "service" in text and _contains_any(
            text, "outcome", "failed", "incomplete", "record"
        )

    significant_words = {
        word
        for word in re.findall(r"[a-z0-9]+", label.lower())
        if len(word) >= 4 and word not in {"current", "complete", "applicable"}
    }
    return bool(significant_words.intersection(re.findall(r"[a-z0-9]+", text)))


def _addresses_action(action_type: str, body: str) -> bool:
    text = body.lower()
    terms = {
        "reverse_duplicate_charge": ("reversal", "reverse", "duplicate charge"),
        "issue_refund": ("refund",),
        "start_verified_recovery": ("recovery", "account access"),
        "apply_service_correction": ("correction", "service outcome"),
    }.get(action_type, tuple(action_type.split("_")))
    return _contains_any(text, *terms)


def _contains_any(text: str, *values: str) -> bool:
    return any(value in text for value in values)
