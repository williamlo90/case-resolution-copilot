"""Normalize persisted product evidence; this module has no oracle or label dependency."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.resolution import ActionReadback, payload_digest
from app.evaluation.case_resolution_v2.contracts import ActionExpectation, PolicyExpectation
from app.evaluation.case_resolution_v2.models import (
    Approval,
    Completion,
    Escalation,
    Fact,
    Observation,
    Operation,
    Scenario,
)
from app.evaluation.case_resolution_v2.storage import digest
from app.evaluation.phase4_scenario_runtime import product_case_id
from app.persistence.models import (
    CaseActionAttemptModel,
    CaseActionModel,
    CaseActionReceiptModel,
    CaseModel,
    CasePolicyEvidenceModel,
    CaseProposedActionModel,
    CaseReviewDecisionModel,
    CaseReviewSnapshotModel,
    ConversationMessageModel,
    GovernedPolicyClauseModel,
    GovernedPolicyVersionModel,
    MembershipModel,
    OrganizationModel,
    PolicyModel,
)
from app.persistence.models.resolution import CaseResolutionEventModel


def _facts(decision: dict[str, Any]) -> tuple[dict[str, Fact], list[str]]:
    facts: dict[str, Fact] = {}
    claims: list[str] = []
    conflicted: set[str] = set()
    for row in decision["facts"]:
        statement = row["statement"]
        source = row["source"]
        if ": " not in statement or " / " not in source:
            claims.append(statement)
            continue
        label, value = statement.split(": ", 1)
        source_id, reference = source.split(" / ", 1)
        if source_id != reference or not value.endswith("."):
            claims.append(statement)
            continue
        key = label.lower().replace(" ", "_")
        value = value[:-1]
        if key in conflicted:
            claims.append(statement)
            continue
        previous = facts.get(key)
        if previous is not None and previous.value != value:
            # Preserve the contradiction as a claim so it cannot become a clean fact.
            claims.append(statement)
            facts.pop(key)
            conflicted.add(key)
            continue
        facts[key] = Fact(value=value, evidence_ids=(source_id,))
    return facts, claims


def _intent(
    action_type: str, target: str, tenant: str, parameters: dict[str, str]
) -> ActionExpectation:
    normalized = dict(parameters)
    if normalized.pop("external_reference", None) != target:
        raise ValueError("Product action target and reference disagree")
    return ActionExpectation(
        action_type=action_type,
        target=target,
        tenant_id=tenant,
        consequential_parameters=normalized,
        approval="human_required",
        expected_effect_count=1,
        readback_predicates=("exact_target_parameters_one_effect",),
    )


def _role(session: Session, organization_id: Any, actor_id: str) -> str:
    member = session.scalar(
        select(MembershipModel).where(
            MembershipModel.organization_id == organization_id,
            MembershipModel.public_id == actor_id,
        )
    )
    if member is None or member.status != "active":
        raise ValueError("The attesting actor is not an active tenant member")
    return str(member.role)


def observe(
    *,
    session: Session,
    scenario: Scenario,
    decision: dict[str, Any],
    observed_at: datetime | None = None,
) -> Observation:
    """Read only case-scoped product records. A missing proof stays missing."""
    case = session.scalar(select(CaseModel).where(CaseModel.public_id == product_case_id(scenario)))
    if case is None:
        raise ValueError("Product case does not exist")
    organization = session.get(OrganizationModel, case.organization_id)
    if organization is None or organization.public_id != scenario.tenant_id:
        raise ValueError("Product case belongs to another tenant")
    if observed_at is None:
        observed_at = datetime.now(UTC)
    if observed_at.utcoffset() is None:
        raise ValueError("Observation timestamp must be aware")
    facts, claims = _facts(decision)
    evidence = list(
        session.scalars(
            select(CasePolicyEvidenceModel).where(
                CasePolicyEvidenceModel.case_id == case.id,
                CasePolicyEvidenceModel.organization_id == case.organization_id,
            )
        )
    )
    source_basis = {row["policy_id"]: row["date_basis"] for row in scenario.policies}
    policies: list[PolicyExpectation] = []
    for row in evidence:
        policy = session.get(PolicyModel, row.policy_id)
        version = session.get(GovernedPolicyVersionModel, row.policy_version_id)
        clause = session.get(GovernedPolicyClauseModel, row.clause_id)
        if policy is None or version is None or clause is None:
            raise ValueError("Persisted policy binding is incomplete")
        if policy.public_id not in source_basis:
            raise ValueError("Product cited a policy outside the scheduled scenario")
        if version.effective_from is None:
            raise ValueError("Policy has no dated authority")
        policies.append(
            PolicyExpectation(
                policy_id=policy.public_id,
                version=version.version,
                clause_id=clause.public_id,
                effective_from=version.effective_from,
                effective_to=version.effective_to,
                applicable_at=row.recorded_at,
                date_basis=source_basis[policy.public_id],
            )
        )
    proposed_rows = list(
        session.scalars(
            select(CaseProposedActionModel).where(
                CaseProposedActionModel.case_id == case.id,
                CaseProposedActionModel.organization_id == case.organization_id,
            )
        )
    )
    proposed = tuple(
        _intent(row.type, row.parameters["external_reference"], scenario.tenant_id, row.parameters)
        for row in proposed_rows
        if row.type != "request_information"
    )
    events = list(
        session.scalars(
            select(CaseResolutionEventModel)
            .where(
                CaseResolutionEventModel.case_id == case.id,
                CaseResolutionEventModel.organization_id == case.organization_id,
            )
            .order_by(CaseResolutionEventModel.occurred_at, CaseResolutionEventModel.id)
        )
    )
    operations: list[Operation] = []
    verified_event_to_operation: dict[str, str] = {}
    for action in session.scalars(
        select(CaseActionModel).where(
            CaseActionModel.case_id == case.id,
            CaseActionModel.organization_id == case.organization_id,
        )
    ):
        matching_proposal = next(
            (row for row in proposed_rows if row.id == action.proposed_action_id), None
        )
        review = session.get(CaseReviewDecisionModel, action.review_decision_id)
        snapshot = session.get(CaseReviewSnapshotModel, action.review_snapshot_id)
        if (
            matching_proposal is None
            or review is None
            or snapshot is None
            or review.decision != "approve"
            or review.snapshot_fingerprint != snapshot.snapshot_fingerprint
            or action.typed_parameters != matching_proposal.parameters
            or action.proposal_version_id != matching_proposal.proposal_version_id
        ):
            raise ValueError("Product action is not bound to its approved proposal")
        intent = _intent(action.type, action.target, scenario.tenant_id, action.typed_parameters)
        attempt = session.scalar(
            select(CaseActionAttemptModel)
            .where(CaseActionAttemptModel.action_id == action.id)
            .order_by(CaseActionAttemptModel.started_at)
        )
        receipt = session.scalar(
            select(CaseActionReceiptModel).where(CaseActionReceiptModel.action_id == action.id)
        )
        if attempt is None or receipt is None:
            raise ValueError("Product operation has no durable attempt or receipt")
        verified_event = next(
            (
                event
                for event in reversed(events)
                if event.kind == "action_verified"
                and event.data.get("action_id") == action.public_id
            ),
            None,
        )
        readback = None
        if verified_event is not None and verified_event.data.get("proof") is not None:
            if verified_event.data.get("payload_hash") != payload_digest(
                action.type,
                action.target,
                action.typed_parameters,
                action.impact_amount,
                action.impact_currency,
            ):
                raise ValueError("Persisted proof is bound to another action payload")
            proof = ActionReadback.model_validate(verified_event.data["proof"])
            reduced = proof.model_dump(mode="python")
            observed_parameters = dict(proof.observed_parameters)
            if observed_parameters.pop("external_reference", None) != action.target:
                raise ValueError("Target readback references another object")
            reduced["observed_parameters"] = observed_parameters
            readback = ActionReadback.model_validate(reduced)
            verified_event_to_operation[str(verified_event.id)] = action.idempotency_key
        operations.append(
            Operation(
                intent=intent,
                operation_id=action.idempotency_key,
                external_reference=receipt.external_reference,
                executed_at=attempt.started_at,
                approval=Approval(
                    role=_role(session, case.organization_id, review.reviewer_public_id),
                    tenant_id=scenario.tenant_id,
                    # Adapter attestation: the product snapshot and action links were checked
                    # above before canonicalizing the consequential intent for the V2 scorer.
                    payload_sha256=digest(intent),
                    approved_at=review.decided_at,
                    expires_at=action.authorization_expires_at,
                ),
                readback=readback,
            )
        )
    completion_event = next(
        (event for event in reversed(events) if event.kind == "completed"), None
    )
    completion = None
    if completion_event is not None:
        ids = tuple(
            verified_event_to_operation[key]
            for key in completion_event.data.get("verification_ids", [])
            if key in verified_event_to_operation
        )
        completion = Completion(
            event_id=str(completion_event.id),
            tenant_id=scenario.tenant_id,
            occurred_at=completion_event.occurred_at,
            verified_operation_ids=ids,
            communication_reference=completion_event.data["communication_reference"],
            attested_role=_role(session, case.organization_id, completion_event.actor_id),
        )
    route = next((event for event in reversed(events) if event.kind == "escalation_routed"), None)
    ack = next(
        (event for event in reversed(events) if event.kind == "escalation_acknowledged"), None
    )
    escalation = None
    if route is not None and ack is not None:
        escalation = Escalation(
            queue=route.data["queue"],
            tenant_id=scenario.tenant_id,
            routing_id=str(route.id),
            assigned_actor=route.data["destination_member_id"],
            acknowledged_actor=ack.actor_id,
            acknowledged_role=_role(session, case.organization_id, ack.actor_id),
            routed_at=route.occurred_at,
            acknowledged_at=ack.occurred_at,
        )
    terminal = "verified_resolution" if completion else "safe_escalation" if escalation else "open"
    if operations:
        policies = [
            policy.model_copy(update={"applicable_at": operations[0].executed_at})
            if policy.date_basis == "execution"
            else policy
            for policy in policies
        ]
    policy_status = {
        "relevant": "applicable",
        "conflicting": "conflicting",
    }.get(decision["analysis"]["policy_status"], "missing")
    gaps = tuple(
        row["label"].lower().replace(" ", "_")
        for row in decision["missing_information"]
        if row["blocking"]
    )
    if completion and operations:
        resolution = operations[0].intent.action_type
    elif escalation and gaps:
        resolution = "escalate_for_" + gaps[0]
    else:
        resolution = "unresolved"
    semantic = {
        "resolution": resolution,
        "customer_communication": "required"
        if completion
        or session.scalar(
            select(ConversationMessageModel.id).where(
                ConversationMessageModel.case_id == case.id,
                ConversationMessageModel.organization_id == case.organization_id,
                ConversationMessageModel.author_type == "member",
                ConversationMessageModel.internal.is_(False),
            )
        )
        else "absent",
        "authority": "supervisor_approval" if completion else "do_not_execute",
    }
    claims.append(decision["response_draft"]["body"])
    return Observation(
        version="case-resolution-v2-observation-1",
        case_id=scenario.case_id,
        input_sha256=digest(scenario),
        tenant_id=scenario.tenant_id,
        observed_at=observed_at,
        status="observed",
        facts=facts,
        gaps=gaps,
        policies=tuple(policies),
        policy_status=policy_status,
        semantic_assertions=semantic,
        disposition="resolve"
        if completion
        else "escalate"
        if escalation
        else "request_information",
        proposed_actions=proposed,
        operations=tuple(operations),
        claims=tuple(claims),
        terminal=terminal,
        completion=completion,
        escalation=escalation,
        human_touches=int(bool(operations)) + int(bool(completion or escalation)),
    )
