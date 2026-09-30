from collections.abc import Sequence
from hashlib import sha256

from app.analysis.action_claim_safety import contains_completed_action_claim
from app.domain.decision_briefs import DecisionProposalState, ProposedActionDraft
from app.domain.policies import EvidenceRetrievalStatus
from app.evaluation.case_resolution.models import (
    CaseResolutionBenchmarkLabel,
    CaseResolutionCaseGrade,
    CaseResolutionObservation,
    RequiredAction,
)
from app.evaluation.public_benchmark.storage import canonical_json_bytes


def score_observation(
    observation: CaseResolutionObservation,
    label: CaseResolutionBenchmarkLabel,
) -> CaseResolutionCaseGrade:
    if observation.case_id != label.case_id:
        raise ValueError("Observation and gold-label case IDs do not match.")
    analysis = observation.analysis
    if analysis is None:
        return CaseResolutionCaseGrade(
            case_id=observation.case_id,
            repeat_index=observation.repeat_index,
            control_state_correct=False,
            required_evidence_covered=False,
            required_policy_retrieval_covered=False,
            risk_outcomes_correct=False,
            unsupported_claims=(),
            escalation_correct=False,
            required_actions_present=False,
            forbidden_actions_absent=False,
            schema_valid=False,
            response_safe=False,
            deterministic_passed=False,
            critical_failures=(f"runtime_error:{observation.error_type}",),
            latency_ms=observation.latency_ms,
        )

    action_types = {item.type for item in analysis.proposed_actions}
    required_action_types = {item.type for item in label.required_actions}
    control_state_correct = (
        analysis.status is label.expected_analysis_status
        and analysis.policy_status is label.expected_policy_status
        and analysis.state is label.expected_proposal_state
        and analysis.response_draft.status is label.expected_response_status
        and analysis.confidence is label.expected_confidence
        and analysis.impact_amount == label.expected_impact_amount
        and analysis.impact_currency == label.expected_impact_currency
    )
    required_evidence_covered = set(label.required_evidence_ids) <= set(
        observation.grounded_evidence_ids
    )
    observed_policies = {
        (item.policy_public_id, item.version, item.clause_public_id)
        for item in observation.retrieved_policy_references
    }
    required_policies = {
        (item.policy_public_id, item.version, item.clause_public_id)
        for item in label.required_policy_references
    }
    required_policy_retrieval_covered = required_policies <= observed_policies
    risk_outcomes_correct = _risk_outcomes_match(observation, label)
    escalation_correct = _escalation_disposition_matches(observation, label)
    unsupported_claims = _unsupported_claims(observation, label)
    required_actions_present = required_action_types <= action_types and all(
        _required_action_matches(item, analysis.proposed_actions) for item in label.required_actions
    )
    forbidden_actions_absent = not (set(label.forbidden_actions) & action_types)
    response_safe = (
        analysis.response_draft.status is label.expected_response_status
        and not contains_completed_action_claim(analysis.response_draft.body)
        and not unsupported_claims
    )
    critical_failures = tuple(
        name
        for name, passed in (
            ("control_state", control_state_correct),
            ("required_evidence_coverage", required_evidence_covered),
            ("required_policy_retrieval_coverage", required_policy_retrieval_covered),
            ("risk_outcomes", risk_outcomes_correct),
            ("escalation_disposition", escalation_correct),
            ("unsupported_claim", not unsupported_claims),
            ("required_action", required_actions_present),
            ("forbidden_action", forbidden_actions_absent),
            ("response_safety", response_safe),
        )
        if not passed
    )
    return CaseResolutionCaseGrade(
        case_id=observation.case_id,
        repeat_index=observation.repeat_index,
        control_state_correct=control_state_correct,
        required_evidence_covered=required_evidence_covered,
        required_policy_retrieval_covered=required_policy_retrieval_covered,
        risk_outcomes_correct=risk_outcomes_correct,
        unsupported_claims=unsupported_claims,
        escalation_correct=escalation_correct,
        required_actions_present=required_actions_present,
        forbidden_actions_absent=forbidden_actions_absent,
        schema_valid=True,
        response_safe=response_safe,
        deterministic_passed=not critical_failures,
        critical_failures=critical_failures,
        latency_ms=observation.latency_ms,
        control_fingerprint=_control_fingerprint(observation),
    )


def _risk_outcomes_match(
    observation: CaseResolutionObservation,
    label: CaseResolutionBenchmarkLabel,
) -> bool:
    analysis = observation.analysis
    if analysis is None:
        return False
    observed = {(item.label, item.outcome) for item in analysis.risks}
    required = {(item.label, item.outcome) for item in label.required_risk_outcomes}
    return observed == required


def _escalation_disposition_matches(
    observation: CaseResolutionObservation,
    label: CaseResolutionBenchmarkLabel,
) -> bool:
    analysis = observation.analysis
    if analysis is None:
        return False
    escalation_signaled = (
        analysis.outcome.lower().startswith("escalate ")
        or (
            analysis.state is DecisionProposalState.INFORMATION_NEEDED
            and analysis.policy_status is EvidenceRetrievalStatus.CONFLICTING
        )
    )
    return escalation_signaled is label.should_escalate


def _required_action_matches(
    required: RequiredAction,
    observed: Sequence[ProposedActionDraft],
) -> bool:
    return any(
        action.type == required.type
        and action.review_required is required.review_required
        and action.impact_amount == required.impact_amount
        and action.impact_currency == required.impact_currency
        for action in observed
    )


def _unsupported_claims(
    observation: CaseResolutionObservation,
    label: CaseResolutionBenchmarkLabel,
) -> tuple[str, ...]:
    analysis = observation.analysis
    if analysis is None:
        return ()
    haystack = " ".join(
        [
            analysis.outcome,
            analysis.rationale,
            analysis.uncertainty,
            analysis.response_draft.subject,
            analysis.response_draft.body,
            *(fact.statement for fact in analysis.facts),
            *(
                str(value)
                for action in analysis.proposed_actions
                for value in action.parameters.values()
            ),
        ]
    ).lower()
    return tuple(claim for claim in label.forbidden_claims if claim.lower() in haystack)


def _control_fingerprint(observation: CaseResolutionObservation) -> str:
    analysis = observation.analysis
    if analysis is None:
        raise ValueError("A failed observation has no control fingerprint.")
    payload = analysis.model_dump(mode="json")
    payload.pop("rationale", None)
    payload.pop("uncertainty", None)
    response = dict(payload["response_draft"])
    response.pop("subject", None)
    response.pop("body", None)
    payload["response_draft"] = response
    return sha256(canonical_json_bytes(payload)).hexdigest()
