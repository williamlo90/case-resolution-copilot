from app.domain.actions import (
    ActionAttemptOutcome,
    ActionCommand,
    ActionConflict,
    ActionExecutionBlocked,
    ActionExecutionLease,
    ActionQueueItemRecord,
    ActionSideEffectState,
    ActionStatus,
    ActionVersionConflict,
)
from app.integrations.action_gateway import (
    ActionGatewayError,
    ActionGatewayReceipt,
)
from app.persistence.models import (
    CaseActionAttemptModel,
    OrganizationModel,
    utc_now,
)

from ._base import (
    ActionRepositoryBase,
    _blocker_message,
    _hash,
    _stable_public_id,
)


class ActionExecutionRepository(ActionRepositoryBase):
    def prepare_execution(
        self,
        *,
        organization_public_id: str,
        action_public_id: str,
        actor_id: str,
        expected_version: int,
        command: ActionCommand,
        correlation_id: str,
    ) -> ActionExecutionLease:
        if command not in {ActionCommand.EXECUTE, ActionCommand.RETRY_SAFE}:
            raise ActionConflict("This command cannot create an execution attempt.")
        action = self._required_action(
            organization_public_id,
            action_public_id,
            for_update=True,
        )
        now = utc_now()
        self._reconcile_abandoned(action=action, now=now)
        if action.version != expected_version:
            raise ActionVersionConflict(
                expected_version=expected_version,
                current_version=action.version,
            )
        blocker = self._effective_blocker(action, now=now)
        if blocker is not None:
            raise ActionExecutionBlocked(
                blocker,
                _blocker_message(blocker),
            )
        if command is ActionCommand.EXECUTE and action.status != ActionStatus.READY.value:
            raise ActionConflict("Only a ready action can be executed.")
        if command is ActionCommand.RETRY_SAFE:
            if action.status != ActionStatus.FAILED_SAFE.value:
                raise ActionConflict("Only an action proven to have made no change can be retried.")
            if not self._retry_is_safe(action):
                raise ActionConflict("A safe retry requires proof that the target was not changed.")
        member = self._active_member(
            organization_id=action.organization_id,
            actor_id=actor_id,
        )
        connection = self._required_connection(action)
        attempt_number = action.attempt_count + 1
        attempt = CaseActionAttemptModel(
            public_id=_stable_public_id(
                "AT",
                action.public_id,
                str(attempt_number),
            ),
            organization_id=action.organization_id,
            case_id=action.case_id,
            action_id=action.id,
            actor_id=member.id,
            actor_public_id=member.public_id,
            actor_name=member.name,
            actor_role=member.role,
            legacy_tool_attempt_id=None,
            number=attempt_number,
            command=command.value,
            outcome=ActionAttemptOutcome.RUNNING.value,
            side_effect_state=ActionSideEffectState.NOT_ATTEMPTED.value,
            detail="The controlled action is being sent to its target.",
            error_code=None,
            request_fingerprint=_hash(
                {
                    "action_id": action.public_id,
                    "type": action.type,
                    "target": action.target,
                    "parameters": action.typed_parameters,
                    "idempotency_key": action.idempotency_key,
                    "command": command.value,
                }
            ),
            response_fingerprint=None,
            started_at=now,
            finished_at=None,
        )
        action.status = ActionStatus.RUNNING.value
        action.execution_blocker = None
        action.owner_id = member.id
        action.owner_public_id = member.public_id
        action.owner_name = member.name
        action.attempt_count = attempt_number
        action.version += 1
        action.updated_at = now
        self._session.add(attempt)
        self._session.flush()
        self._add_audit(
            action=action,
            event_type="case.action_started",
            actor_type="member",
            actor_id=member.public_id,
            summary="A controlled action attempt was started.",
            data={
                "attempt_id": attempt.public_id,
                "attempt_number": attempt.number,
                "command": command.value,
                "idempotency_key": action.idempotency_key,
            },
            correlation_id=correlation_id,
            occurred_at=now,
        )
        organization = self._session.get(OrganizationModel, action.organization_id)
        if organization is None:
            raise ActionConflict("The action organization is missing.")
        return ActionExecutionLease(
            action_id=action.id,
            action_public_id=action.public_id,
            action_version=action.version,
            attempt_id=attempt.id,
            attempt_public_id=attempt.public_id,
            organization_public_id=organization.public_id,
            action_type=action.type,
            target=action.target,
            parameters=dict(action.typed_parameters),
            idempotency_key=action.idempotency_key,
            adapter_key=connection.adapter_key,
            provider_type=connection.provider_type,
        )

    def finish_execution_success(
        self,
        *,
        lease: ActionExecutionLease,
        receipt: ActionGatewayReceipt,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        action, attempt = self._execution_models(lease)
        if attempt.outcome != ActionAttemptOutcome.RUNNING.value:
            if action.status == ActionStatus.COMPLETED.value:
                return self._queue_item(action, now=utc_now())
            raise ActionConflict("This action attempt already has a final outcome.")
        if receipt.idempotency_key != action.idempotency_key:
            raise ActionConflict("The target receipt does not match this action's idempotency key.")
        now = utc_now()
        stored_receipt = self._record_receipt(
            action=action,
            attempt=attempt,
            receipt=receipt,
            now=now,
        )
        attempt.outcome = ActionAttemptOutcome.SUCCEEDED.value
        attempt.side_effect_state = ActionSideEffectState.CONFIRMED.value
        attempt.detail = "The target confirmed the change and returned an attributable receipt."
        attempt.response_fingerprint = _hash(receipt.model_dump(mode="json"))
        attempt.finished_at = now
        action.status = ActionStatus.COMPLETED.value
        action.execution_blocker = None
        action.observed_outcome = (
            f"Target confirmed {stored_receipt.external_reference} "
            f"with status {stored_receipt.status}."
        )
        action.version += 1
        action.updated_at = now
        self._advance_case_after_completion(action, now=now)
        self._add_audit(
            action=action,
            event_type="case.action_completed",
            actor_type="member",
            actor_id=attempt.actor_public_id,
            summary="The target confirmed the controlled action.",
            data={
                "attempt_id": attempt.public_id,
                "receipt_id": stored_receipt.public_id,
                "external_reference": stored_receipt.external_reference,
                "duplicate_receipt": receipt.duplicate,
            },
            correlation_id=correlation_id,
            occurred_at=now,
        )
        self._session.flush()
        return self._queue_item(action, now=now)

    def finish_execution_error(
        self,
        *,
        lease: ActionExecutionLease,
        error: ActionGatewayError,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        action, attempt = self._execution_models(lease)
        if attempt.outcome != ActionAttemptOutcome.RUNNING.value:
            return self._queue_item(action, now=utc_now())
        now = utc_now()
        safe_failure = error.side_effect_state in {
            ActionSideEffectState.NOT_ATTEMPTED,
            ActionSideEffectState.NONE,
        }
        attempt.outcome = (
            ActionAttemptOutcome.FAILED_BEFORE_CHANGE.value
            if safe_failure
            else ActionAttemptOutcome.UNKNOWN.value
        )
        attempt.side_effect_state = error.side_effect_state.value
        attempt.detail = str(error)
        attempt.error_code = error.code
        attempt.response_fingerprint = _hash(
            {
                "code": error.code,
                "detail": str(error),
                "side_effect_state": error.side_effect_state.value,
                "retryable": error.retryable,
            }
        )
        attempt.finished_at = now
        action.status = (
            ActionStatus.FAILED_SAFE.value if safe_failure else ActionStatus.OUTCOME_UNKNOWN.value
        )
        action.observed_outcome = str(error)
        action.version += 1
        action.updated_at = now
        self._add_audit(
            action=action,
            event_type=(
                "case.action_failed_safe" if safe_failure else "case.action_outcome_unknown"
            ),
            actor_type="member",
            actor_id=attempt.actor_public_id,
            summary=(
                "The target made no change."
                if safe_failure
                else "The target outcome could not be confirmed."
            ),
            data={
                "attempt_id": attempt.public_id,
                "error_code": error.code,
                "side_effect_state": error.side_effect_state.value,
                "blind_retry_blocked": not safe_failure,
            },
            correlation_id=correlation_id,
            occurred_at=now,
        )
        self._session.flush()
        return self._queue_item(action, now=now)
