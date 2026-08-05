from app.api.schemas.actions import (
    ActionAttemptResponse,
    ActionAuthorityResponse,
    ActionDetailResponse,
    ActionReceiptResponse,
    ActionReconciliationResponse,
    ActionSummaryResponse,
    ActionTargetConnectionResponse,
    ApprovedProposalReferenceResponse,
)
from app.api.schemas.common import ActorSummaryResponse, MoneyResponse
from app.domain.actions import ActionQueueItemRecord
from app.domain.identity import ActorContext
from app.services.action_service import available_action_commands


def present_action_summary(
    item: ActionQueueItemRecord,
    *,
    organization_id: str,
) -> ActionSummaryResponse:
    action = item.bundle.action
    return ActionSummaryResponse(
        id=action.public_id,
        organization_id=organization_id,
        case_id=item.bundle.case_public_id,
        type=action.type,
        label=action.label,
        target=action.target,
        impact=(
            MoneyResponse(
                amount=action.impact_amount,
                currency=action.impact_currency,
            )
            if action.impact_amount is not None and action.impact_currency is not None
            else None
        ),
        status=action.status,
        execution_blocker=item.effective_blocker,
        attempt_count=action.attempt_count,
        owner=(
            ActorSummaryResponse(
                id=action.owner_public_id,
                name=action.owner_name,
            )
            if action.owner_public_id is not None and action.owner_name is not None
            else None
        ),
        updated_at=action.updated_at,
        recovery_required=item.recovery_required,
        version=action.version,
    )


def present_action_detail(
    item: ActionQueueItemRecord,
    *,
    actor: ActorContext,
) -> ActionDetailResponse:
    bundle = item.bundle
    action = bundle.action
    return ActionDetailResponse(
        action=present_action_summary(
            item,
            organization_id=actor.organization_id,
        ),
        approved_proposal=ApprovedProposalReferenceResponse(
            id=bundle.proposal_public_id,
            version=bundle.proposal_version,
            review_id=bundle.review_public_id,
            approved_at=bundle.approved_at,
            snapshot_fingerprint=bundle.review_snapshot_fingerprint,
        ),
        authority=ActionAuthorityResponse(
            actor=ActorSummaryResponse(
                id=bundle.approved_by_public_id,
                name=bundle.approved_by_name,
            ),
            role=_role_label(bundle.approved_by_role.value),
            rule=bundle.approval_rule,
        ),
        typed_parameters=action.typed_parameters,
        target_connection=ActionTargetConnectionResponse(
            id=bundle.connection.public_id,
            name=bundle.connection.name,
            environment=bundle.connection.environment,
            health=bundle.connection.health,
            last_checked_at=bundle.connection.last_checked_at,
        ),
        idempotency_key=action.idempotency_key,
        attempts=[
            ActionAttemptResponse(
                id=attempt.public_id,
                number=attempt.number,
                started_at=attempt.started_at,
                finished_at=attempt.finished_at,
                actor=ActorSummaryResponse(
                    id=attempt.actor_public_id,
                    name=attempt.actor_name,
                ),
                command=attempt.command,
                outcome=attempt.outcome,
                side_effect_state=attempt.side_effect_state,
                detail=attempt.detail,
            )
            for attempt in bundle.attempts
        ],
        receipt=(
            ActionReceiptResponse(
                id=bundle.receipt.public_id,
                provider=bundle.receipt.provider,
                external_reference=bundle.receipt.external_reference,
                status=bundle.receipt.status,
                recorded_at=bundle.receipt.recorded_at,
            )
            if bundle.receipt is not None
            else None
        ),
        reconciliations=[
            ActionReconciliationResponse(
                id=reconciliation.public_id,
                outcome=reconciliation.outcome,
                detail=reconciliation.detail,
                external_reference=reconciliation.external_reference,
                checked_by=ActorSummaryResponse(
                    id=reconciliation.actor_public_id,
                    name=reconciliation.actor_name,
                ),
                checked_at=reconciliation.checked_at,
            )
            for reconciliation in bundle.reconciliations
        ],
        expected_outcome=action.expected_outcome,
        observed_outcome=action.observed_outcome,
        execution_blocker=item.effective_blocker,
        available_commands=available_action_commands(
            actor=actor,
            item=item,
        ),
    )


def _role_label(role: str) -> str:
    return {
        "specialist": "Support specialist",
        "supervisor": "Support supervisor",
        "administrator": "Operations administrator",
        "auditor": "Auditor",
    }.get(role, role.replace("_", " ").title())
