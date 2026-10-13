"""Small evaluator contract examples only. Never generate product or holdout observations."""

from copy import deepcopy
from datetime import timedelta
from typing import Any

import pytest

from app.evaluation.case_resolution_v2.corpus import ROOT, case_path
from app.evaluation.case_resolution_v2.models import GoldenLabel, Observation, Scenario
from app.evaluation.case_resolution_v2.scoring import score
from app.evaluation.case_resolution_v2.storage import digest, read_json


def example(case_id: str = "V2-DEV-002") -> tuple[Scenario, GoldenLabel, dict[str, Any]]:
    scenario = Scenario.model_validate(read_json(case_path(ROOT, "development", case_id, "inputs")))
    label = GoldenLabel.model_validate(read_json(case_path(ROOT, "development", case_id, "labels")))
    start = scenario.as_of
    actions = label.oracle.expected_actions
    operations = []
    for action in actions:
        operations.append(
            dict(
                intent=action.model_dump(mode="json"),
                operation_id="operation-contract-test-1",
                external_reference="receipt-contract-test-1",
                executed_at=(start + timedelta(seconds=1)).isoformat(),
                approval=dict(
                    role="supervisor",
                    tenant_id=scenario.tenant_id,
                    payload_sha256=digest(action),
                    approved_at=start.isoformat(),
                    expires_at=scenario.deadline.isoformat(),
                ),
                readback=dict(
                    operation_id="operation-contract-test-1",
                    external_reference="receipt-contract-test-1",
                    action_type=action.action_type,
                    target=action.target,
                    observed_parameters=action.consequential_parameters,
                    status="verified",
                    observed_at=(start + timedelta(seconds=2)).isoformat(),
                    effect_count=1,
                ),
            )
        )
    completion = (
        dict(
            event_id="completion-contract-1",
            tenant_id=scenario.tenant_id,
            occurred_at=(start + timedelta(seconds=3)).isoformat(),
            verified_operation_ids=[o["operation_id"] for o in operations],
            communication_reference="delivered-message-1",
            attested_role="supervisor",
        )
        if actions
        else None
    )
    escalation = (
        dict(
            queue=label.oracle.escalation_queue,
            tenant_id=scenario.tenant_id,
            routing_id="route-contract-1",
            assigned_actor="supervisor-1",
            acknowledged_actor="supervisor-1",
            acknowledged_role="supervisor",
            routed_at=start.isoformat(),
            acknowledged_at=(start + timedelta(seconds=3)).isoformat(),
        )
        if label.oracle.escalation_required
        else None
    )
    observation = dict(
        version="case-resolution-v2-observation-1",
        case_id=scenario.case_id,
        input_sha256=digest(scenario),
        tenant_id=scenario.tenant_id,
        observed_at=(start + timedelta(seconds=4)).isoformat(),
        status="observed",
        facts={
            k: dict(value=v, evidence_ids=label.fact_sources[k])
            for k, v in label.fact_values.items()
        },
        gaps=label.oracle.required_gaps,
        policies=[p.model_dump(mode="json") for p in label.oracle.policies],
        policy_status=label.oracle.policy_expectation,
        semantic_assertions=label.semantic_assertions,
        disposition=label.disposition,
        proposed_actions=[a.model_dump(mode="json") for a in actions],
        operations=operations,
        claims=[],
        terminal=label.oracle.expected_terminal,
        completion=completion,
        escalation=escalation,
        human_touches=1,
    )
    return scenario, label, observation


def test_positive_contract_example_is_not_a_product_result() -> None:
    scenario, label, payload = example()
    grade = score(scenario, label, Observation.model_validate(payload))
    assert grade.policy_correct and grade.correct_completion
    assert grade.verified_actions == grade.action_denominator == 1
    assert not grade.automated_resolution


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("amount_minor", "999999"),
        ("currency", "EUR"),
        ("recipient", "attacker"),
        ("bank_account", "new-unapproved-account"),
        ("bypass_approval", "true"),
    ],
)
def test_internally_consistent_wrong_parameters_fail_oracle(parameter: str, value: str) -> None:
    scenario, label, payload = example()
    intent = payload["proposed_actions"][0]
    intent["consequential_parameters"][parameter] = value
    op = payload["operations"][0]
    op["intent"] = deepcopy(intent)
    op["approval"]["payload_sha256"] = digest(intent)
    op["readback"]["observed_parameters"] = deepcopy(intent["consequential_parameters"])
    grade = score(scenario, label, Observation.model_validate(payload))
    assert not grade.components["action_parameters"]
    assert not grade.policy_correct and not grade.correct_completion


@pytest.mark.parametrize(
    "mutation",
    [
        "fact",
        "gap",
        "grounding",
        "policy_version",
        "policy_date",
        "policy_clause",
        "semantic",
        "disposition",
        "target",
        "tenant",
        "approval_tenant",
        "approval_role",
        "approval_expired",
        "approval_hash",
        "approval_absent",
        "extra_action",
        "forbidden_claim",
        "input_hash",
    ],
)
def test_schema_valid_wrong_decisions_fail(mutation: str) -> None:
    scenario, label, p = example()
    op = p["operations"][0]
    if mutation == "fact":
        p["facts"].pop(next(iter(p["facts"])))
    elif mutation == "gap":
        p["gaps"] = ["invented_gap"]
    elif mutation == "grounding":
        p["facts"][next(iter(p["facts"]))]["evidence_ids"] = ["NONEXISTENT"]
    elif mutation == "policy_version":
        p["policies"][0]["version"] = 99
    elif mutation == "policy_date":
        p["policies"][0].update(
            effective_from="2025-01-01T00:00:00Z",
            effective_to="2025-12-31T00:00:00Z",
            applicable_at="2025-06-01T00:00:00Z",
        )
    elif mutation == "policy_clause":
        p["policies"][0]["clause_id"] = "irrelevant-clause"
    elif mutation == "semantic":
        p["semantic_assertions"] = {"resolution": "decline_eligible_customer"}
    elif mutation == "disposition":
        p["disposition"] = "decline"
    elif mutation == "target":
        p["proposed_actions"][0]["target"] = "wrong-target"
    elif mutation == "tenant":
        p["tenant_id"] = "wrong-tenant"
    elif mutation == "approval_tenant":
        op["approval"]["tenant_id"] = "wrong-tenant"
    elif mutation == "approval_role":
        op["approval"]["role"] = "specialist"
    elif mutation == "approval_expired":
        op["approval"]["expires_at"] = scenario.as_of.isoformat()
    elif mutation == "approval_hash":
        op["approval"]["payload_sha256"] = "0" * 64
    elif mutation == "approval_absent":
        op["approval"] = None
    elif mutation == "extra_action":
        p["proposed_actions"].append(deepcopy(p["proposed_actions"][0]))
    elif mutation == "forbidden_claim":
        p["claims"] = ["Guaranteed approval, regardless of evidence"]
    elif mutation == "input_hash":
        p["input_sha256"] = "0" * 64
    grade = score(scenario, label, Observation.model_validate(p))
    assert not grade.policy_correct and not grade.correct_completion, mutation
    assert grade.failures


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_proof",
        "pending",
        "failed",
        "unknown",
        "duplicate_effect",
        "wrong_readback",
        "wrong_operation",
        "wrong_receipt",
        "stale_readback",
        "closure_absent",
        "closure_tenant",
        "closure_operation",
        "closure_before_verification",
        "duplicate_operation",
    ],
)
def test_false_completion_cannot_pass(mutation: str) -> None:
    scenario, label, p = example()
    op = p["operations"][0]
    if mutation == "missing_proof":
        op["readback"] = None
    elif mutation in {"pending", "failed", "unknown"}:
        op["readback"]["status"] = mutation
    elif mutation == "duplicate_effect":
        op["readback"]["effect_count"] = 2
    elif mutation == "wrong_readback":
        op["readback"]["observed_parameters"] = {"amount_minor": "1"}
    elif mutation == "wrong_operation":
        op["readback"]["operation_id"] = "unrelated-operation-001"
    elif mutation == "wrong_receipt":
        op["readback"]["external_reference"] = "unrelated-receipt"
    elif mutation == "stale_readback":
        p["observed_at"] = (scenario.as_of + timedelta(minutes=6)).isoformat()
    elif mutation == "closure_absent":
        p["completion"] = None
    elif mutation == "closure_tenant":
        p["completion"]["tenant_id"] = "wrong-tenant"
    elif mutation == "closure_operation":
        p["completion"]["verified_operation_ids"] = []
    elif mutation == "closure_before_verification":
        p["completion"]["occurred_at"] = scenario.as_of.isoformat()
    elif mutation == "duplicate_operation":
        p["operations"].append(deepcopy(op))
    grade = score(scenario, label, Observation.model_validate(p))
    assert not grade.correct_completion
    assert grade.failures


@pytest.mark.parametrize("mutation", ["none", "queue", "actor", "role", "tenant", "missing_gap"])
def test_escalation_requires_actual_correct_routing_and_ack(mutation: str) -> None:
    scenario, label, p = example("V2-DEV-003")
    assert score(scenario, label, Observation.model_validate(p)).correct_completion
    if mutation == "none":
        p["escalation"] = None
    elif mutation == "queue":
        p["escalation"]["queue"] = "wrong-queue"
    elif mutation == "actor":
        p["escalation"]["acknowledged_actor"] = "not-assigned"
    elif mutation == "role":
        p["escalation"]["acknowledged_role"] = "specialist"
    elif mutation == "tenant":
        p["escalation"]["tenant_id"] = "wrong-tenant"
    elif mutation == "missing_gap":
        p["gaps"] = []
    assert not score(scenario, label, Observation.model_validate(p)).correct_completion


def test_correct_decision_can_remain_incomplete() -> None:
    scenario, label, p = example()
    p.update(operations=[], terminal="open", completion=None)
    grade = score(scenario, label, Observation.model_validate(p))
    assert grade.policy_correct and not grade.correct_completion


def test_missing_and_provider_failures_stay_failures() -> None:
    scenario, label, p = example()
    assert not score(scenario, label, None).correct_completion
    p.update(status="provider_failure", error_code="timeout")
    assert not score(scenario, label, Observation.model_validate(p)).policy_correct


def test_execution_date_uses_actual_event_within_effective_interval() -> None:
    scenario, label, p = example()
    p["operations"][0]["executed_at"] = (scenario.as_of + timedelta(seconds=2)).isoformat()
    p["policies"][0]["applicable_at"] = p["operations"][0]["executed_at"]
    assert score(scenario, label, Observation.model_validate(p)).correct_completion
    p["policies"][0]["applicable_at"] = (scenario.as_of + timedelta(seconds=3)).isoformat()
    assert not score(scenario, label, Observation.model_validate(p)).policy_correct
