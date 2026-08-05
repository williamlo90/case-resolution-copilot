from collections.abc import Mapping
from decimal import Decimal

from app.domain.decision_briefs import (
    DecisionBriefRecord,
    DecisionProposalState,
    ResponseSuggestionStatus,
    RiskOutcome,
)
from app.domain.identity import MemberRole
from app.domain.policies import EvidenceRetrievalStatus
from app.domain.reviews import (
    ApprovalRuleSnapshot,
    ReviewDecision,
    ReviewDecisionNotAllowed,
    ReviewPolicyState,
    ReviewSubmissionNotAllowed,
    ReviewUncertainty,
)
from app.domain.settings import DEFAULT_ADMINISTRATOR_FINANCIAL_LIMITS

DEFAULT_ADMIN_FINANCIAL_LIMITS = DEFAULT_ADMINISTRATOR_FINANCIAL_LIMITS


def assess_review_rule(
    brief: DecisionBriefRecord,
    *,
    financial_limits: Mapping[str, Decimal] | None = None,
    rule_version: int = 1,
) -> ApprovalRuleSnapshot:
    version = brief.version
    policy_status = brief.run.policy_status
    limits = (
        DEFAULT_ADMIN_FINANCIAL_LIMITS
        if financial_limits is None
        else financial_limits
    )
    risk_text = " ".join(
        f"{risk.id} {risk.label} {risk.explanation}".lower() for risk in version.risks
    )
    administrator_required = (
        policy_status is EvidenceRetrievalStatus.CONFLICTING
        or _financial_admin_required(brief, limits)
        or "privacy" in risk_text
        or "compliance" in risk_text
    )
    if administrator_required:
        return ApprovalRuleSnapshot(
            public_id="APR-ADMINISTRATOR",
            name="Administrator decision required",
            explanation=_review_reason(
                brief,
                administrator=True,
                financial_limits=limits,
            ),
            required_role=MemberRole.ADMINISTRATOR,
            version=rule_version,
        )
    return ApprovalRuleSnapshot(
        public_id="APR-SUPERVISOR",
        name="Supervisor decision required",
        explanation=_review_reason(
            brief,
            administrator=False,
            financial_limits=limits,
        ),
        required_role=MemberRole.SUPERVISOR,
        version=rule_version,
    )


def review_policy_state(brief: DecisionBriefRecord) -> ReviewPolicyState:
    if brief.run.policy_status is EvidenceRetrievalStatus.RELEVANT:
        return ReviewPolicyState.SUPPORTED
    if brief.run.policy_status is EvidenceRetrievalStatus.CONFLICTING:
        return ReviewPolicyState.POSSIBLE_CONFLICT
    return ReviewPolicyState.MISSING


def review_uncertainty(brief: DecisionBriefRecord) -> ReviewUncertainty:
    return {
        "high": ReviewUncertainty.LOW,
        "medium": ReviewUncertainty.MEDIUM,
        "low": ReviewUncertainty.HIGH,
    }[brief.version.confidence.value]


def require_review_submission(brief: DecisionBriefRecord) -> None:
    has_review_action = any(action.review_required for action in brief.proposed_actions)
    blocked_policy = brief.run.policy_status is not EvidenceRetrievalStatus.RELEVANT
    if brief.version.state not in {
        DecisionProposalState.READY_FOR_REVIEW,
        DecisionProposalState.INFORMATION_NEEDED,
    }:
        raise ReviewSubmissionNotAllowed(
            "This resolution is not in a state that can be submitted for review."
        )
    if not has_review_action and not blocked_policy:
        raise ReviewSubmissionNotAllowed("This resolution does not require a supervisor decision.")


def role_satisfies(*, actor_role: MemberRole | None, required_role: MemberRole) -> bool:
    if actor_role is MemberRole.ADMINISTRATOR:
        return True
    return actor_role is required_role


def allowed_decisions(
    *,
    brief: DecisionBriefRecord,
    actor_role: MemberRole | None,
    required_role: MemberRole,
) -> list[ReviewDecision]:
    if not role_satisfies(actor_role=actor_role, required_role=required_role):
        return []
    decisions = [
        ReviewDecision.REQUEST_CHANGES,
        ReviewDecision.REJECT,
        ReviewDecision.ESCALATE,
    ]
    return [ReviewDecision.APPROVE, *decisions] if approval_is_safe(brief) else decisions


def approval_is_safe(brief: DecisionBriefRecord) -> bool:
    return (
        brief.run.policy_status is EvidenceRetrievalStatus.RELEVANT
        and brief.version.state is DecisionProposalState.READY_FOR_REVIEW
        and brief.response_draft.status is not ResponseSuggestionStatus.BLOCKED
        and all(
            risk.outcome in {RiskOutcome.PASSED, RiskOutcome.REQUIRES_REVIEW}
            for risk in brief.version.risks
        )
    )


def require_decision_allowed(
    *,
    decision: ReviewDecision,
    available_decisions: list[ReviewDecision],
) -> None:
    if decision not in available_decisions:
        raise ReviewDecisionNotAllowed(
            "That decision is not available for this review and current authority."
        )


def _review_reason(
    brief: DecisionBriefRecord,
    *,
    administrator: bool,
    financial_limits: Mapping[str, Decimal],
) -> str:
    version = brief.version
    if brief.run.policy_status is EvidenceRetrievalStatus.CONFLICTING:
        return "Conflicting policy authority requires an administrator decision."
    if _financial_admin_required(brief, financial_limits):
        return (
            "The proposed financial impact exceeds the default review limit or uses "
            "a currency without a configured limit."
        )
    risk_text = " ".join(f"{risk.label} {risk.explanation}".lower() for risk in version.risks)
    if "privacy" in risk_text or "compliance" in risk_text:
        return "Privacy or compliance risk requires an administrator decision."
    if version.impact_amount is not None:
        return "The proposed financial change requires a supervisor decision."
    if administrator:
        return "This high-risk resolution requires an administrator decision."
    return "This customer-impacting resolution requires a supervisor decision."


def _financial_admin_required(
    brief: DecisionBriefRecord,
    financial_limits: Mapping[str, Decimal],
) -> bool:
    amount = brief.version.impact_amount
    if amount is None:
        return False
    currency = brief.version.impact_currency
    if currency is None:
        return True
    limit = financial_limits.get(currency)
    return limit is None or amount >= limit
