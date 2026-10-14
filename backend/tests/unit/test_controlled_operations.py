import json
from decimal import Decimal
from hashlib import sha256

import pytest

from app.analysis.deterministic_decision_engine import DeterministicDecisionEngine
from app.analysis.sop_rules import validate_rule_scope
from app.domain.cases import CaseCategory, CaseWorkspaceRecord, SourceFreshness
from app.domain.controlled_operations import OPERATIONS, operation_gaps
from app.domain.policies import EvidenceRetrievalResult, EvidenceRetrievalStatus
from app.evaluation.decision_brief_fixtures import (
    build_evaluation_evidence,
    build_evaluation_workspace,
)


def operation_workspace(action: str) -> tuple[CaseWorkspaceRecord, EvidenceRetrievalResult]:
    spec = OPERATIONS[action]
    workspace = build_evaluation_workspace("CS-2047")
    workspace.case.category = CaseCategory(spec.category)
    workspace.case.source_freshness = SourceFreshness.CURRENT
    workspace.case.impact_amount = None if spec.scope else Decimal("10.00")
    workspace.case.impact_currency = None if spec.scope else "USD"
    workspace.business_contexts = workspace.business_contexts[:1]
    context = workspace.business_contexts[0]
    context.source_freshness = SourceFreshness.CURRENT
    context.fields = {
        "requested_operation": action,
        "requested_target": "SYNTHETIC-OBJECT-1",
        "original_recipient": "SYNTHETIC-OWNER-1",
        "authorized_recipient": "SYNTHETIC-OWNER-1",
        "authorized_reason_code": "documented-entitlement",
        "authorized_amount_minor": "1000",
        "authorized_currency": "USD",
        "authorized_access_scope": spec.scope or "none",
        "authorized_preserve_owner": "true",
        **dict(spec.conditions),
        **{f"requested_{key}": "synthetic-new-value" for key in spec.value_fields},
    }
    if action == "change_recovery_email":
        context.fields["requested_new_email"] = "owner@example.test"
        context.fields["challenge_destination"] = "owner@example.test"
    evidence = build_evaluation_evidence(workspace, EvidenceRetrievalStatus.RELEVANT)
    rule = {
        "schema_version": 1,
        "rules": [
            {
                "kind": "controlled_operation",
                "action_type": action,
                "max_amount_minor": 0 if spec.scope else 1000,
                "currency": "USD",
            }
        ],
    }
    for bundle in evidence.evidence:
        bundle.version.case_categories = [spec.category]
        bundle.version.source_text += "\n```case-resolution-rules\n" + json.dumps(rule) + "\n```"
        bundle.version.content_hash = sha256(bundle.version.source_text.encode()).hexdigest()
        bundle.evidence.policy_content_hash = bundle.version.content_hash
    return workspace, evidence


@pytest.mark.parametrize("action", list(OPERATIONS))
def test_typed_operation_runs_through_actual_decision_engine(action: str) -> None:
    workspace, evidence = operation_workspace(action)
    result = DeterministicDecisionEngine().analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint="4" * 64,
    )
    assert not result.missing_information
    assert result.state.value == "ready_for_review"
    assert len(result.proposed_actions) == 1
    draft = result.proposed_actions[0]
    assert draft.type == action
    assert draft.review_required
    assert draft.parameters["external_reference"] == "SYNTHETIC-OBJECT-1"
    for key in OPERATIONS[action].value_fields:
        assert draft.parameters[key] == workspace.business_contexts[0].fields[f"requested_{key}"]


@pytest.mark.parametrize("mutation", ["recipient", "value", "condition", "scope", "authority"])
def test_identity_change_abstains_on_incomplete_or_changed_inputs(mutation: str) -> None:
    workspace, evidence = operation_workspace("change_recovery_email")
    fields = workspace.business_contexts[0].fields
    if mutation == "recipient":
        fields["authorized_recipient"] = "ANOTHER-OWNER"
    elif mutation == "value":
        fields.pop("requested_new_email")
    elif mutation == "condition":
        fields["email_challenge"] = "failed"
    elif mutation == "scope":
        fields["authorized_access_scope"] = "all_sessions"
    else:
        for bundle in evidence.evidence:
            bundle.version.source_text = "Unstructured prose is not an execution grant."
            bundle.version.content_hash = sha256(bundle.version.source_text.encode()).hexdigest()
            bundle.evidence.policy_content_hash = bundle.version.content_hash
    result = DeterministicDecisionEngine().analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint="4" * 64,
    )
    assert result.state.value == "information_needed"
    assert all(action.type == "request_information" for action in result.proposed_actions)


def test_amount_currency_and_published_limit_are_independent_constraints() -> None:
    workspace, evidence = operation_workspace("refund_course_fee")
    workspace.case.impact_amount = Decimal("10.01")
    workspace.business_contexts[0].fields["authorized_amount_minor"] = "1001"
    result = DeterministicDecisionEngine().analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint="4" * 64,
    )
    assert result.state.value == "information_needed"
    workspace.business_contexts[0].fields["authorized_currency"] = "EUR"
    assert "matching_case_currency" in operation_gaps(workspace, "refund_course_fee")


def test_conflicting_operation_names_do_not_fall_back_to_generic_refund() -> None:
    workspace, evidence = operation_workspace("refund_course_fee")
    other = workspace.business_contexts[0].model_copy(deep=True)
    other.fields["requested_operation"] = "refund_unstarted_premium"
    workspace.business_contexts.append(other)
    result = DeterministicDecisionEngine().analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint="4" * 64,
    )
    assert result.state.value == "information_needed"


def test_operation_cannot_publish_under_an_unrelated_category() -> None:
    _, evidence = operation_workspace("rename_account")
    with pytest.raises(ValueError):
        validate_rule_scope(evidence.evidence[0].version.source_text, ["refund_request"])
