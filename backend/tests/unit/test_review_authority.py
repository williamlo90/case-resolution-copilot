from decimal import Decimal

import pytest
from pydantic import ValidationError

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
    ReviewSubmission,
    ReviewUncertainty,
)
from app.security.review_authority import (
    allowed_decisions,
    assess_review_rule,
    require_decision_allowed,
    role_satisfies,
)
from tests.builders import valid_decision_brief


def _brief(
    *,
    policy_status: EvidenceRetrievalStatus = EvidenceRetrievalStatus.RELEVANT,
    state: DecisionProposalState = DecisionProposalState.READY_FOR_REVIEW,
    impact: Decimal | None = Decimal("125.00"),
    currency: str | None = "USD",
    risk_outcome: RiskOutcome = RiskOutcome.REQUIRES_REVIEW,
    risk_label: str = "Financial change",
    response_status: ResponseSuggestionStatus = ResponseSuggestionStatus.READY,
) -> DecisionBriefRecord:
    return valid_decision_brief(
        policy_status=policy_status,
        state=state,
        response_status=response_status,
        impact_amount=impact,
        impact_currency=currency,
        risk_outcome=risk_outcome,
        risk_label=risk_label,
    )


def test_standard_review_requires_supervisor_and_admin_satisfies_rule() -> None:
    rule = assess_review_rule(_brief())

    assert rule.required_role is MemberRole.SUPERVISOR
    assert role_satisfies(
        actor_role=MemberRole.SUPERVISOR,
        required_role=rule.required_role,
    )
    assert role_satisfies(
        actor_role=MemberRole.ADMINISTRATOR,
        required_role=rule.required_role,
    )
    assert not role_satisfies(
        actor_role=MemberRole.SPECIALIST,
        required_role=rule.required_role,
    )


@pytest.mark.parametrize(
    "brief",
    [
        _brief(impact=Decimal("1000.00")),
        _brief(policy_status=EvidenceRetrievalStatus.CONFLICTING),
        _brief(risk_label="Privacy disclosure"),
    ],
)
def test_high_impact_conflict_or_sensitive_risk_requires_admin(
    brief: DecisionBriefRecord,
) -> None:
    assert assess_review_rule(brief).required_role is MemberRole.ADMINISTRATOR


def test_financial_authority_uses_currency_specific_limits_and_fails_closed() -> None:
    below_idr_limit = assess_review_rule(_brief(impact=Decimal("14000000.00"), currency="IDR"))
    at_idr_limit = assess_review_rule(_brief(impact=Decimal("15000000.00"), currency="IDR"))
    unknown_currency = assess_review_rule(_brief(impact=Decimal("125.00"), currency="JPY"))

    assert below_idr_limit.required_role is MemberRole.SUPERVISOR
    assert at_idr_limit.required_role is MemberRole.ADMINISTRATOR
    assert unknown_currency.required_role is MemberRole.ADMINISTRATOR


def test_financial_authority_uses_versioned_organization_limits() -> None:
    below_configured_limit = assess_review_rule(
        _brief(impact=Decimal("99.99"), currency="USD"),
        financial_limits={"USD": Decimal("100.00")},
        rule_version=4,
    )
    at_configured_limit = assess_review_rule(
        _brief(impact=Decimal("100.00"), currency="USD"),
        financial_limits={"USD": Decimal("100.00")},
        rule_version=4,
    )

    assert below_configured_limit.required_role is MemberRole.SUPERVISOR
    assert below_configured_limit.version == 4
    assert at_configured_limit.required_role is MemberRole.ADMINISTRATOR
    assert at_configured_limit.version == 4


def test_approval_is_only_available_for_safe_supported_snapshot() -> None:
    safe = allowed_decisions(
        brief=_brief(),
        actor_role=MemberRole.SUPERVISOR,
        required_role=MemberRole.SUPERVISOR,
    )
    missing_policy = allowed_decisions(
        brief=_brief(policy_status=EvidenceRetrievalStatus.MISSING),
        actor_role=MemberRole.SUPERVISOR,
        required_role=MemberRole.SUPERVISOR,
    )
    incomplete_risk = allowed_decisions(
        brief=_brief(risk_outcome=RiskOutcome.INFORMATION_NEEDED),
        actor_role=MemberRole.SUPERVISOR,
        required_role=MemberRole.SUPERVISOR,
    )

    assert ReviewDecision.APPROVE in safe
    assert ReviewDecision.APPROVE not in missing_policy
    assert ReviewDecision.APPROVE not in incomplete_risk
    assert ReviewDecision.REQUEST_CHANGES in missing_policy
    assert ReviewDecision.ESCALATE in incomplete_risk


def test_decision_is_rejected_when_not_in_server_owned_options() -> None:
    with pytest.raises(ReviewDecisionNotAllowed):
        require_decision_allowed(
            decision=ReviewDecision.APPROVE,
            available_decisions=[ReviewDecision.REQUEST_CHANGES],
        )


def test_review_submission_requires_complete_money_pair() -> None:
    values = {
        "expected_case_version": 1,
        "proposal_version": 1,
        "review_reason": "Human review is required.",
        "policy_state": ReviewPolicyState.SUPPORTED,
        "uncertainty": ReviewUncertainty.MEDIUM,
        "impact_amount": Decimal("125.00"),
        "proposal_fingerprint": "a" * 64,
        "context_fingerprint": "b" * 64,
        "evidence_fingerprint": "c" * 64,
        "risk_fingerprint": "d" * 64,
        "risk_rule_version": "risk-v1",
        "snapshot_fingerprint": "e" * 64,
        "approval_rule": ApprovalRuleSnapshot(
            public_id="APR-SUPERVISOR",
            name="Supervisor decision required",
            explanation="A human must approve this customer-impacting action.",
            required_role=MemberRole.SUPERVISOR,
            version=1,
        ),
    }

    with pytest.raises(ValidationError, match="must be supplied together"):
        ReviewSubmission.model_validate(values)
