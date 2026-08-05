from uuid import uuid4

from sqlalchemy import select

from app.domain.actions import (
    ActionAttemptOutcome,
    ActionConflict,
    ActionExecutionBlocked,
    ActionExecutionBlocker,
    ActionNotFound,
    ActionQueueItemRecord,
    ActionReconciliationLease,
    ActionStatus,
    ActionVersionConflict,
    ManualActionOutcome,
    ReconciliationOutcome,
    reconciliation_outcome_for_lookup,
    reconciliation_outcome_for_manual_record,
)
from app.integrations.action_gateway import (
    ActionLookupResult,
)
from app.persistence.models import (
    CaseActionModel,
    CaseActionReconciliationModel,
    OrganizationModel,
    utc_now,
)

from ._base import (
    _RECOVERY_STATUSES,
    ActionRepositoryBase,
    _stable_public_id,
)


class ActionRecoveryRepository(ActionRepositoryBase):
    def prepare_reconciliation(
        self,
        *,
        organization_public_id: str,
        action_public_id: str,
        actor_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> ActionReconciliationLease:
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
        if action.status not in _RECOVERY_STATUSES:
            raise ActionConflict(
                "Reconciliation is available only when the target outcome is unknown."
            )
        connection = self._required_connection(action)
        if connection.adapter_key == "unconfigured":
            raise ActionExecutionBlocked(
                ActionExecutionBlocker.CONNECTION_UNAVAILABLE,
                "Configure this connection before checking the target.",
            )
        attempt = self._latest_attempt(action)
        if attempt is None or attempt.outcome != ActionAttemptOutcome.UNKNOWN.value:
            raise ActionConflict("No unknown execution attempt is available to reconcile.")
        running = self._session.scalar(
            select(CaseActionReconciliationModel).where(
                CaseActionReconciliationModel.organization_id == action.organization_id,
                CaseActionReconciliationModel.action_id == action.id,
                CaseActionReconciliationModel.outcome == ReconciliationOutcome.RUNNING.value,
            )
        )
        if running is not None:
            raise ActionConflict("A reconciliation check is already running.")
        member = self._active_member(
            organization_id=action.organization_id,
            actor_id=actor_id,
        )
        reconciliation = CaseActionReconciliationModel(
            public_id=_stable_public_id(
                "RC",
                action.public_id,
                str(action.version),
                str(uuid4()),
            ),
            organization_id=action.organization_id,
            case_id=action.case_id,
            action_id=action.id,
            actor_id=member.id,
            actor_public_id=member.public_id,
            actor_name=member.name,
            outcome=ReconciliationOutcome.RUNNING.value,
            detail="The target is being checked without issuing another write.",
            external_reference=None,
            checked_at=now,
        )
        action.version += 1
        action.updated_at = now
        self._session.add(reconciliation)
        self._session.flush()
        self._add_audit(
            action=action,
            event_type="case.action_reconciliation_started",
            actor_type="member",
            actor_id=member.public_id,
            summary="A read-only target reconciliation was started.",
            data={"reconciliation_id": reconciliation.public_id},
            correlation_id=correlation_id,
            occurred_at=now,
        )
        organization = self._session.get(OrganizationModel, action.organization_id)
        receipt = self._receipt(action)
        if organization is None:
            raise ActionConflict("The action organization is missing.")
        return ActionReconciliationLease(
            action_id=action.id,
            action_public_id=action.public_id,
            action_version=action.version,
            reconciliation_id=reconciliation.id,
            organization_public_id=organization.public_id,
            action_type=action.type,
            target=action.target,
            parameters=dict(action.typed_parameters),
            idempotency_key=action.idempotency_key,
            external_reference=(receipt.external_reference if receipt is not None else None),
            adapter_key=connection.adapter_key,
            provider_type=connection.provider_type,
        )

    def finish_reconciliation(
        self,
        *,
        lease: ActionReconciliationLease,
        result: ActionLookupResult,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        action = self._session.scalar(
            select(CaseActionModel).where(CaseActionModel.id == lease.action_id).with_for_update()
        )
        reconciliation = self._session.scalar(
            select(CaseActionReconciliationModel)
            .where(
                CaseActionReconciliationModel.id == lease.reconciliation_id,
                CaseActionReconciliationModel.action_id == lease.action_id,
            )
            .with_for_update()
        )
        if action is None or reconciliation is None:
            raise ActionNotFound("The reconciliation lease was not found.")
        if reconciliation.outcome != ReconciliationOutcome.RUNNING.value:
            return self._queue_item(action, now=utc_now())
        attempt = self._latest_attempt(action)
        if attempt is None:
            raise ActionConflict("The action attempt is missing.")
        now = utc_now()
        reconciliation_outcome = reconciliation_outcome_for_lookup(
            found=result.found,
            absence_is_terminal=result.absence_is_terminal,
        )
        if reconciliation_outcome is ReconciliationOutcome.CONFIRMED_COMPLETED:
            if result.receipt is None:
                raise ActionConflict(
                    "The target reported a change without an attributable receipt."
                )
            receipt = self._record_receipt(
                action=action,
                attempt=attempt,
                receipt=result.receipt,
                now=now,
            )
            reconciliation.outcome = ReconciliationOutcome.CONFIRMED_COMPLETED.value
            reconciliation.external_reference = receipt.external_reference
            action.status = ActionStatus.COMPLETED.value
            action.observed_outcome = result.detail
            self._advance_case_after_completion(action, now=now)
        elif reconciliation_outcome is ReconciliationOutcome.CONFIRMED_ABSENT:
            reconciliation.outcome = ReconciliationOutcome.CONFIRMED_ABSENT.value
            action.status = ActionStatus.FAILED_SAFE.value
            action.observed_outcome = result.detail
        else:
            reconciliation.outcome = ReconciliationOutcome.STILL_UNKNOWN.value
            action.status = ActionStatus.OUTCOME_UNKNOWN.value
            action.observed_outcome = result.detail
        reconciliation.detail = result.detail
        reconciliation.checked_at = now
        action.version += 1
        action.updated_at = now
        self._add_audit(
            action=action,
            event_type="case.action_reconciled",
            actor_type="member",
            actor_id=reconciliation.actor_public_id,
            summary="The target was checked without issuing another write.",
            data={
                "reconciliation_id": reconciliation.public_id,
                "outcome": reconciliation.outcome,
                "external_reference": reconciliation.external_reference,
            },
            correlation_id=correlation_id,
            occurred_at=now,
        )
        self._session.flush()
        return self._queue_item(action, now=now)

    def record_manual_outcome(
        self,
        *,
        organization_public_id: str,
        action_public_id: str,
        actor_id: str,
        expected_version: int,
        outcome: ManualActionOutcome,
        reason: str,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        action = self._required_action(
            organization_public_id,
            action_public_id,
            for_update=True,
        )
        if action.version != expected_version:
            raise ActionVersionConflict(
                expected_version=expected_version,
                current_version=action.version,
            )
        if action.status not in _RECOVERY_STATUSES:
            raise ActionConflict("A manual outcome can only resolve an unknown target result.")
        latest_attempt = self._latest_attempt(action)
        if latest_attempt is None or latest_attempt.outcome != ActionAttemptOutcome.UNKNOWN.value:
            raise ActionConflict(
                "This recovery item does not have an unknown target outcome to resolve."
            )
        member = self._active_member(
            organization_id=action.organization_id,
            actor_id=actor_id,
        )
        now = utc_now()
        reconciliation_outcome = reconciliation_outcome_for_manual_record(outcome)
        reconciliation = CaseActionReconciliationModel(
            public_id=_stable_public_id(
                "RC",
                action.public_id,
                "manual",
                str(action.version),
            ),
            organization_id=action.organization_id,
            case_id=action.case_id,
            action_id=action.id,
            actor_id=member.id,
            actor_public_id=member.public_id,
            actor_name=member.name,
            outcome=reconciliation_outcome.value,
            detail=reason,
            external_reference=None,
            checked_at=now,
        )
        action.status = (
            ActionStatus.COMPLETED.value
            if outcome is ManualActionOutcome.COMPLETED
            else ActionStatus.OUTCOME_UNKNOWN.value
        )
        action.observed_outcome = reason
        action.version += 1
        action.updated_at = now
        if outcome is ManualActionOutcome.COMPLETED:
            self._advance_case_after_completion(action, now=now)
        self._session.add(reconciliation)
        self._add_audit(
            action=action,
            event_type="case.action_manual_outcome_recorded",
            actor_type="member",
            actor_id=member.public_id,
            summary="A human-verified target outcome was recorded.",
            data={
                "reconciliation_id": reconciliation.public_id,
                "outcome": outcome.value,
                "reason": reason,
            },
            correlation_id=correlation_id,
            occurred_at=now,
        )
        self._session.flush()
        return self._queue_item(action, now=now)

    def escalate(
        self,
        *,
        organization_public_id: str,
        action_public_id: str,
        actor_id: str,
        expected_version: int,
        reason: str,
        correlation_id: str,
    ) -> ActionQueueItemRecord:
        action = self._required_action(
            organization_public_id,
            action_public_id,
            for_update=True,
        )
        if action.version != expected_version:
            raise ActionVersionConflict(
                expected_version=expected_version,
                current_version=action.version,
            )
        if action.status not in {
            ActionStatus.FAILED_SAFE.value,
            ActionStatus.OUTCOME_UNKNOWN.value,
            ActionStatus.RECOVERY_REQUIRED.value,
        }:
            raise ActionConflict("Only failed or uncertain actions can be escalated for recovery.")
        member = self._active_member(
            organization_id=action.organization_id,
            actor_id=actor_id,
        )
        now = utc_now()
        action.status = ActionStatus.RECOVERY_REQUIRED.value
        action.observed_outcome = reason
        action.owner_id = member.id
        action.owner_public_id = member.public_id
        action.owner_name = member.name
        action.version += 1
        action.updated_at = now
        self._add_audit(
            action=action,
            event_type="case.action_recovery_escalated",
            actor_type="member",
            actor_id=member.public_id,
            summary="The action was escalated for manual recovery.",
            data={"reason": reason},
            correlation_id=correlation_id,
            occurred_at=now,
        )
        self._session.flush()
        return self._queue_item(action, now=now)
