from typing import Protocol

from app.domain.actions import (
    ActionCommand,
    ActionExecutionBlocker,
    ActionNotFound,
    ActionPageRecord,
    ActionQueueItemRecord,
    ActionSideEffectState,
    ActionStatus,
    ManualActionOutcome,
)
from app.domain.identity import ActorContext, Permission
from app.integrations.action_gateway import (
    ActionGateway,
    ActionGatewayError,
    ActionGatewayRequest,
    ActionLookupResult,
)
from app.persistence.action_repository import ActionRepository
from app.persistence.database import Database
from app.security.authorization import require_permission


class ActionQueryStore(Protocol):
    def get(
        self,
        *,
        organization_public_id: str,
        action_public_id: str,
    ) -> ActionQueueItemRecord | None: ...

    def list(
        self,
        *,
        organization_public_id: str,
        status: str | None,
        recovery_required: bool | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ActionPageRecord: ...


class ActionQueryService:
    def __init__(self, store: ActionQueryStore) -> None:
        self._store = store

    def get(
        self,
        *,
        actor: ActorContext,
        action_id: str,
    ) -> ActionQueueItemRecord:
        require_permission(actor, Permission.ACTION_READ)
        item = self._store.get(
            organization_public_id=actor.organization_id,
            action_public_id=action_id,
        )
        if item is None:
            raise ActionNotFound("The action was not found.")
        if (
            item.effective_blocker is None
            and item.bundle.action.status in {ActionStatus.READY, ActionStatus.FAILED_SAFE}
            and not actor.can(Permission.ACTION_EXECUTE)
        ):
            return item.model_copy(
                update={
                    "effective_blocker": ActionExecutionBlocker.PERMISSION,
                }
            )
        return item

    def list(
        self,
        *,
        actor: ActorContext,
        status: str | None,
        recovery_required: bool | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ActionPageRecord:
        require_permission(actor, Permission.ACTION_READ)
        return self._store.list(
            organization_public_id=actor.organization_id,
            status=status,
            recovery_required=recovery_required,
            query=query,
            cursor=cursor,
            limit=limit,
        )


class ActionMaterializationService:
    def __init__(self, repository: ActionRepository) -> None:
        self._repository = repository

    def materialize(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
        correlation_id: str,
    ) -> None:
        self._repository.materialize_approved_review(
            organization_public_id=organization_public_id,
            review_public_id=review_public_id,
            correlation_id=correlation_id,
        )


class ActionCommandService:
    def __init__(self, database: Database, gateway: ActionGateway) -> None:
        self._database = database
        self._gateway = gateway

    def execute(
        self,
        *,
        actor: ActorContext,
        action_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        return self._execute(
            actor=actor,
            action_id=action_id,
            expected_version=expected_version,
            command=ActionCommand.EXECUTE,
            correlation_id=correlation_id,
        )

    def retry_safe(
        self,
        *,
        actor: ActorContext,
        action_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        return self._execute(
            actor=actor,
            action_id=action_id,
            expected_version=expected_version,
            command=ActionCommand.RETRY_SAFE,
            correlation_id=correlation_id,
        )

    def reconcile(
        self,
        *,
        actor: ActorContext,
        action_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        require_permission(actor, Permission.ACTION_RECONCILE)
        with self._database.session() as session:
            lease = ActionRepository(session).prepare_reconciliation(
                organization_public_id=actor.organization_id,
                action_public_id=action_id,
                actor_id=actor.actor_id,
                expected_version=expected_version,
                correlation_id=correlation_id,
            )
        request = ActionGatewayRequest(
            action_id=lease.action_public_id,
            action_type=lease.action_type,
            target=lease.target,
            parameters=lease.parameters,
            idempotency_key=lease.idempotency_key,
        )
        try:
            result = self._gateway.reconcile(
                adapter_key=lease.adapter_key,
                provider_type=lease.provider_type,
                request=request,
                external_reference=lease.external_reference,
            )
        except Exception:
            result = ActionLookupResult(
                found=None,
                receipt=None,
                detail=(
                    "The target could not be checked. The outcome remains unknown "
                    "and retry is still blocked."
                ),
            )
        with self._database.session() as session:
            return ActionRepository(session).finish_reconciliation(
                lease=lease,
                result=result,
                correlation_id=correlation_id,
            )

    def record_manual_outcome(
        self,
        *,
        actor: ActorContext,
        action_id: str,
        expected_version: int,
        outcome: ManualActionOutcome,
        reason: str,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        require_permission(actor, Permission.ACTION_RECONCILE)
        with self._database.session() as session:
            return ActionRepository(session).record_manual_outcome(
                organization_public_id=actor.organization_id,
                action_public_id=action_id,
                actor_id=actor.actor_id,
                expected_version=expected_version,
                outcome=outcome,
                reason=reason,
                correlation_id=correlation_id,
            )

    def escalate(
        self,
        *,
        actor: ActorContext,
        action_id: str,
        expected_version: int,
        reason: str,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        require_permission(actor, Permission.ACTION_RECONCILE)
        with self._database.session() as session:
            return ActionRepository(session).escalate(
                organization_public_id=actor.organization_id,
                action_public_id=action_id,
                actor_id=actor.actor_id,
                expected_version=expected_version,
                reason=reason,
                correlation_id=correlation_id,
            )

    def _execute(
        self,
        *,
        actor: ActorContext,
        action_id: str,
        expected_version: int,
        command: ActionCommand,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        require_permission(actor, Permission.ACTION_EXECUTE)
        with self._database.session() as session:
            lease = ActionRepository(session).prepare_execution(
                organization_public_id=actor.organization_id,
                action_public_id=action_id,
                actor_id=actor.actor_id,
                expected_version=expected_version,
                command=command,
                correlation_id=correlation_id,
            )
        request = ActionGatewayRequest(
            action_id=lease.action_public_id,
            action_type=lease.action_type,
            target=lease.target,
            parameters=lease.parameters,
            idempotency_key=lease.idempotency_key,
        )
        try:
            receipt = self._gateway.execute(
                adapter_key=lease.adapter_key,
                provider_type=lease.provider_type,
                request=request,
            )
        except ActionGatewayError as exc:
            with self._database.session() as session:
                return ActionRepository(session).finish_execution_error(
                    lease=lease,
                    error=exc,
                    correlation_id=correlation_id,
                )
        except Exception:
            unknown = ActionGatewayError(
                "The target stopped responding before the outcome was known.",
                code="unexpected_gateway_failure",
                side_effect_state=ActionSideEffectState.POSSIBLE,
                retryable=False,
            )
            with self._database.session() as session:
                return ActionRepository(session).finish_execution_error(
                    lease=lease,
                    error=unknown,
                    correlation_id=correlation_id,
                )
        with self._database.session() as session:
            return ActionRepository(session).finish_execution_success(
                lease=lease,
                receipt=receipt,
                correlation_id=correlation_id,
            )


def available_action_commands(
    *,
    actor: ActorContext,
    item: ActionQueueItemRecord,
) -> list[ActionCommand]:
    status = item.bundle.action.status
    latest_attempt = item.bundle.attempts[-1] if item.bundle.attempts else None
    has_unknown_outcome = bool(
        status is ActionStatus.OUTCOME_UNKNOWN
        or (latest_attempt is not None and latest_attempt.outcome.value == "unknown")
    )
    commands: list[ActionCommand] = []
    if actor.can(Permission.ACTION_EXECUTE) and item.effective_blocker is None:
        if status is ActionStatus.READY:
            commands.append(ActionCommand.EXECUTE)
        elif status is ActionStatus.FAILED_SAFE:
            commands.append(ActionCommand.RETRY_SAFE)
    if actor.can(Permission.ACTION_RECONCILE):
        if status is ActionStatus.OUTCOME_UNKNOWN or (
            status is ActionStatus.RECOVERY_REQUIRED and has_unknown_outcome
        ):
            if item.bundle.connection.adapter_key != "unconfigured":
                commands.append(ActionCommand.RECONCILE)
            commands.append(ActionCommand.RECORD_MANUAL_OUTCOME)
            if status is ActionStatus.OUTCOME_UNKNOWN:
                commands.append(ActionCommand.ESCALATE)
        elif status is ActionStatus.FAILED_SAFE:
            commands.append(ActionCommand.ESCALATE)
    return commands
