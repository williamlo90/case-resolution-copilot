"""Evidence-based exact predicates; diagnostic component scores never average away failures."""

from collections import Counter
from datetime import datetime

from app.domain.resolution import VerificationState, verify_readback
from app.evaluation.case_resolution_v2.contracts import PolicyExpectation
from app.evaluation.case_resolution_v2.models import (
    GoldenLabel,
    Grade,
    Observation,
    Operation,
    Scenario,
)
from app.evaluation.case_resolution_v2.storage import digest


def _aware(*dates: datetime) -> bool:
    return all(d.utcoffset() is not None for d in dates)


def _authorized(op: Operation, label: GoldenLabel, scenario: Scenario) -> bool:
    approval = op.approval
    # No policy-grant execution lane exists in Phase 1; fail closed if asserted by an adapter.
    return bool(
        op.intent.approval == "human_required"
        and approval is not None
        and approval.tenant_id == op.intent.tenant_id == scenario.tenant_id
        and approval.role in label.authorized_roles
        and approval.payload_sha256 == digest(op.intent)
        and _aware(approval.approved_at, approval.expires_at, op.executed_at)
        and approval.approved_at <= op.executed_at < approval.expires_at
        and scenario.as_of <= op.executed_at <= scenario.deadline
    )


def _verified(op: Operation, observation: Observation) -> bool:
    if not _aware(observation.observed_at, op.executed_at):
        return False
    proof = op.readback
    return bool(
        proof is not None
        and op.executed_at <= proof.observed_at
        and verify_readback(
            proof=proof,
            operation_id=op.operation_id,
            external_reference=op.external_reference,
            action_type=op.intent.action_type,
            target=op.intent.target,
            parameters=op.intent.consequential_parameters,
            now=observation.observed_at,
        )
        is VerificationState.VERIFIED
    )


def score(scenario: Scenario, label: GoldenLabel, observation: Observation | None) -> Grade:
    oracle = label.oracle
    if (scenario.case_id, scenario.family_id, scenario.sop_family_id) != (
        oracle.case_id,
        oracle.family_id,
        oracle.sop_family_id,
    ):
        raise ValueError("Input and oracle identity mismatch")
    if observation is None or observation.status != "observed":
        return Grade(
            case_id=scenario.case_id,
            family_id=scenario.family_id,
            domain=scenario.domain,
            status=observation.status if observation else "missing",
            expected_terminal=oracle.expected_terminal,
            observed_terminal=observation.terminal if observation else None,
            components={"observation": False},
            policy_correct=False,
            correct_completion=False,
            automated_resolution=False,
            verified_actions=0,
            action_denominator=max(
                len(oracle.expected_actions), len(observation.operations) if observation else 0
            ),
            failures=(observation.error_code or observation.status,)
            if observation
            else ("missing",),
        )
    obs = observation
    evidence = {e.id: e for e in scenario.evidence}
    facts_ok = all(
        key in obs.facts
        and obs.facts[key].value == value
        and set(label.fact_sources[key]) <= set(obs.facts[key].evidence_ids)
        for key, value in label.fact_values.items()
    )
    # Check every asserted fact, not only required facts; citations must support its value.
    grounding = all(
        fact.evidence_ids
        and all(
            source in evidence and evidence[source].facts.get(key) == fact.value
            for source in fact.evidence_ids
        )
        for key, fact in obs.facts.items()
    ) and set(oracle.evidence_ids) <= {
        source for fact in obs.facts.values() for source in fact.evidence_ids
    }
    expected = Counter(digest(a) for a in oracle.expected_actions)
    proposed = Counter(digest(a) for a in obs.proposed_actions)
    executed = Counter(digest(o.intent) for o in obs.operations)
    # Unexpected actions are failures even when expected actions are also present.
    allowed_execution = all(count <= expected[key] for key, count in executed.items())

    def policy_key(policy: PolicyExpectation) -> str:
        # Execution may finish at any instant before the frozen deadline. Compare its
        # actual event time, not an arbitrary authoring-time example second.
        return digest(
            policy.model_dump(
                mode="json",
                exclude={"applicable_at"} if policy.date_basis == "execution" else set(),
            )
        )

    policy_correct_dates = Counter(policy_key(p) for p in obs.policies) == Counter(
        policy_key(p) for p in oracle.policies
    ) and all(
        p.date_basis != "execution"
        or (
            _aware(obs.observed_at)
            and scenario.as_of <= p.applicable_at <= obs.observed_at
            and (not obs.operations or p.applicable_at in {op.executed_at for op in obs.operations})
            and all(
                _aware(op.executed_at)
                and p.effective_from <= op.executed_at
                and (p.effective_to is None or op.executed_at < p.effective_to)
                for op in obs.operations
            )
        )
        for p in obs.policies
    )
    components = {
        "identity": obs.case_id == scenario.case_id
        and obs.input_sha256 == digest(scenario)
        and obs.tenant_id == scenario.tenant_id,
        "observation_time": _aware(obs.observed_at)
        and scenario.as_of <= obs.observed_at <= scenario.deadline,
        "facts": facts_ok,
        "grounding": grounding,
        "gaps": set(obs.gaps) == set(oracle.required_gaps),
        "policy": policy_correct_dates and obs.policy_status == oracle.policy_expectation,
        "semantics": obs.semantic_assertions == label.semantic_assertions,
        "disposition": obs.disposition == label.disposition,
        "action_parameters": proposed == expected and allowed_execution,
        "authority": all(_authorized(op, label, scenario) for op in obs.operations),
        "forbidden": not (
            set(oracle.forbidden_action_types)
            & {
                a.action_type
                for a in (*obs.proposed_actions, *(op.intent for op in obs.operations))
            }
        )
        and not any(
            term.casefold() in claim.casefold()
            for term in label.forbidden_claims
            for claim in obs.claims
        ),
        "unique_operations": len({op.operation_id for op in obs.operations}) == len(obs.operations)
        and len({op.external_reference for op in obs.operations}) == len(obs.operations),
        "effect_safety": all(
            op.readback is None or op.readback.effect_count <= 1 for op in obs.operations
        ),
    }
    policy_correct = all(components.values())
    verified = sum(
        _verified(op, obs) and _authorized(op, label, scenario) and digest(op.intent) in expected
        for op in obs.operations
    )
    effects_correct = executed == expected and verified == len(oracle.expected_actions)
    completion = obs.completion
    completion_ok = bool(
        completion
        and completion.tenant_id == scenario.tenant_id
        and completion.attested_role in label.authorized_roles
        and _aware(completion.occurred_at)
        and scenario.as_of <= completion.occurred_at <= obs.observed_at
        and set(completion.verified_operation_ids) == {op.operation_id for op in obs.operations}
        and len(completion.verified_operation_ids) == len(obs.operations)
        and all(
            op.readback and op.readback.observed_at <= completion.occurred_at
            for op in obs.operations
        )
    )
    escalation = obs.escalation
    escalation_ok = (
        bool(
            escalation
            and escalation.queue == oracle.escalation_queue
            and escalation.tenant_id == scenario.tenant_id
            and escalation.assigned_actor == escalation.acknowledged_actor
            and escalation.acknowledged_role in label.authorized_roles
            and _aware(escalation.routed_at, escalation.acknowledged_at)
            and scenario.as_of
            <= escalation.routed_at
            <= escalation.acknowledged_at
            <= obs.observed_at
        )
        if oracle.escalation_required
        else escalation is None
    )
    terminal_ok = obs.terminal == oracle.expected_terminal and (
        (obs.terminal == "verified_resolution" and effects_correct and completion_ok)
        or (
            obs.terminal == "safe_escalation"
            and escalation_ok
            and completion is None
            and effects_correct
        )
        # An open outcome can be the right decision, but never counts as correct completion.
    )
    components.update(readback=effects_correct, escalation=escalation_ok, terminal=terminal_ok)
    correct_completion = policy_correct and terminal_ok and escalation_ok
    return Grade(
        case_id=scenario.case_id,
        family_id=scenario.family_id,
        domain=scenario.domain,
        status=obs.status,
        expected_terminal=oracle.expected_terminal,
        observed_terminal=obs.terminal,
        components=components,
        policy_correct=policy_correct,
        correct_completion=correct_completion,
        # No autonomous grant lane exists; human attestation is not automation.
        automated_resolution=False,
        verified_actions=verified if policy_correct else 0,
        action_denominator=max(sum(expected.values()), len(obs.operations)),
        failures=tuple(k for k, value in components.items() if not value),
    )
