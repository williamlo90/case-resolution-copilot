from app.domain.decision_briefs import DecisionBriefRecord
from app.services.review_service import (
    proposal_snapshot_fingerprint,
    review_snapshot_fingerprint,
)
from tests.builders import valid_decision_brief


def _brief(
    *,
    action_type: str = "issue_refund",
    context_fingerprint: str = "b" * 64,
    risk_fingerprint: str = "d" * 64,
) -> DecisionBriefRecord:
    return valid_decision_brief(
        action_type=action_type,
        input_fingerprint="a" * 64,
        context_fingerprint=context_fingerprint,
        evidence_fingerprint="c" * 64,
        risk_fingerprint=risk_fingerprint,
    )


def test_proposal_fingerprint_changes_with_action_snapshot() -> None:
    original = proposal_snapshot_fingerprint(_brief())
    changed = proposal_snapshot_fingerprint(_brief(action_type="issue_credit"))

    assert original != changed
    assert len(original) == 64


def test_review_fingerprint_changes_with_context_or_risk_binding() -> None:
    brief = _brief()
    proposal_fingerprint = proposal_snapshot_fingerprint(brief)
    original = review_snapshot_fingerprint(
        case_id="CS-TEST",
        case_version=2,
        brief=brief,
        proposal_fingerprint=proposal_fingerprint,
        approval_rule_id="APR-SUPERVISOR",
        approval_rule_version=1,
    )
    changed_context = review_snapshot_fingerprint(
        case_id="CS-TEST",
        case_version=2,
        brief=_brief(context_fingerprint="e" * 64),
        proposal_fingerprint=proposal_fingerprint,
        approval_rule_id="APR-SUPERVISOR",
        approval_rule_version=1,
    )
    changed_risk = review_snapshot_fingerprint(
        case_id="CS-TEST",
        case_version=2,
        brief=_brief(risk_fingerprint="f" * 64),
        proposal_fingerprint=proposal_fingerprint,
        approval_rule_id="APR-SUPERVISOR",
        approval_rule_version=1,
    )

    assert original != changed_context
    assert original != changed_risk
