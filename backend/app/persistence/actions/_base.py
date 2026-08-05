import base64
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.actions import (
    ActionAttemptOutcome,
    ActionAttemptRecord,
    ActionBundleRecord,
    ActionConflict,
    ActionExecutionBlocker,
    ActionExecutionLease,
    ActionNotFound,
    ActionQueueItemRecord,
    ActionReceiptRecord,
    ActionReconciliationRecord,
    ActionRecord,
    ActionSideEffectState,
    ActionStatus,
    InvalidActionCursor,
    ReconciliationOutcome,
)
from app.domain.connections import ConnectionHealth, ConnectionRecord
from app.domain.identity import ActorMembershipNotFound
from app.integrations.action_gateway import (
    ActionGatewayReceipt,
)
from app.persistence.models import (
    AuditEventModel,
    CaseActionAttemptModel,
    CaseActionModel,
    CaseActionReceiptModel,
    CaseActionReconciliationModel,
    CaseModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseProposedActionModel,
    CaseReviewDecisionModel,
    CaseReviewModel,
    CaseReviewSnapshotModel,
    ConnectionModel,
    MembershipModel,
    OrganizationModel,
)

ACTION_AUTHORIZATION_HOURS = 24
ABANDONED_ACTION_MINUTES = 5
CONNECTION_HEALTH_MAX_AGE_MINUTES = 15

_RECOVERY_STATUSES = {
    ActionStatus.OUTCOME_UNKNOWN.value,
    ActionStatus.RECOVERY_REQUIRED.value,
}


class ActionRepositoryBase:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _queue_item(
        self,
        action: CaseActionModel,
        *,
        now: datetime,
    ) -> ActionQueueItemRecord:
        return ActionQueueItemRecord(
            bundle=self._load_bundle(action),
            effective_blocker=self._effective_blocker(action, now=now),
            recovery_required=action.status in _RECOVERY_STATUSES,
        )

    def _load_bundle(self, action: CaseActionModel) -> ActionBundleRecord:
        case = self._session.get(CaseModel, action.case_id)
        proposal = self._session.get(CaseProposalModel, action.proposal_id)
        version = self._session.get(
            CaseProposalVersionModel,
            action.proposal_version_id,
        )
        review = self._session.get(CaseReviewModel, action.review_id)
        snapshot = self._session.get(
            CaseReviewSnapshotModel,
            action.review_snapshot_id,
        )
        decision = self._session.get(
            CaseReviewDecisionModel,
            action.review_decision_id,
        )
        connection = self._session.get(ConnectionModel, action.connection_id)
        if (
            case is None
            or proposal is None
            or version is None
            or review is None
            or snapshot is None
            or decision is None
            or connection is None
        ):
            raise ActionConflict("The action lineage is incomplete.")
        attempts = list(
            self._session.scalars(
                select(CaseActionAttemptModel)
                .where(
                    CaseActionAttemptModel.organization_id == action.organization_id,
                    CaseActionAttemptModel.action_id == action.id,
                )
                .order_by(CaseActionAttemptModel.number)
            )
        )
        receipt = self._receipt(action)
        reconciliations = list(
            self._session.scalars(
                select(CaseActionReconciliationModel)
                .where(
                    CaseActionReconciliationModel.organization_id == action.organization_id,
                    CaseActionReconciliationModel.action_id == action.id,
                )
                .order_by(CaseActionReconciliationModel.checked_at)
            )
        )
        return ActionBundleRecord(
            action=ActionRecord.model_validate(action),
            case_public_id=case.public_id,
            proposal_public_id=proposal.public_id,
            proposal_version=version.version,
            review_public_id=review.public_id,
            review_snapshot_fingerprint=snapshot.snapshot_fingerprint,
            approved_at=decision.decided_at,
            approved_by_public_id=decision.reviewer_public_id,
            approved_by_name=decision.reviewer_name,
            approved_by_role=decision.reviewer_role,
            approval_rule=snapshot.approval_rule_name,
            connection=ConnectionRecord.model_validate(connection),
            attempts=[ActionAttemptRecord.model_validate(attempt) for attempt in attempts],
            receipt=(ActionReceiptRecord.model_validate(receipt) if receipt is not None else None),
            reconciliations=[
                ActionReconciliationRecord.model_validate(item) for item in reconciliations
            ],
        )

    def _effective_blocker(
        self,
        action: CaseActionModel,
        *,
        now: datetime,
    ) -> ActionExecutionBlocker | None:
        if action.status == ActionStatus.COMPLETED.value or self._receipt(action) is not None:
            return ActionExecutionBlocker.DUPLICATE
        if not action.execution_eligible:
            return ActionExecutionBlocker.STALE_PROPOSAL
        if action.authorization_expires_at <= now:
            return ActionExecutionBlocker.EXPIRED_APPROVAL
        review = self._session.get(CaseReviewModel, action.review_id)
        snapshot = self._session.get(
            CaseReviewSnapshotModel,
            action.review_snapshot_id,
        )
        decision = self._session.get(
            CaseReviewDecisionModel,
            action.review_decision_id,
        )
        case = self._session.get(CaseModel, action.case_id)
        proposal = self._session.get(CaseProposalModel, action.proposal_id)
        version = self._session.get(
            CaseProposalVersionModel,
            action.proposal_version_id,
        )
        if (
            review is None
            or snapshot is None
            or decision is None
            or case is None
            or proposal is None
            or version is None
            or review.status != "approved"
            or decision.decision != "approve"
            or decision.snapshot_fingerprint != snapshot.snapshot_fingerprint
            or not snapshot.execution_eligible
            or case.version != snapshot.case_version
            or proposal.current_version != snapshot.proposal_version
            or proposal.state != "approved"
            or version.version != snapshot.proposal_version
            or version.legacy_proposal_version_id is not None
        ):
            return ActionExecutionBlocker.STALE_PROPOSAL
        connection = self._required_connection(action)
        if (
            not _connection_is_eligible(connection, now=now)
            or action.type not in connection.action_types
        ):
            return ActionExecutionBlocker.CONNECTION_UNAVAILABLE
        return None

    def _retry_is_safe(self, action: CaseActionModel) -> bool:
        latest_reconciliation = self._session.scalar(
            select(CaseActionReconciliationModel)
            .where(
                CaseActionReconciliationModel.organization_id == action.organization_id,
                CaseActionReconciliationModel.action_id == action.id,
            )
            .order_by(CaseActionReconciliationModel.checked_at.desc())
            .limit(1)
        )
        if (
            latest_reconciliation is not None
            and latest_reconciliation.outcome == ReconciliationOutcome.CONFIRMED_ABSENT.value
        ):
            return True
        latest_attempt = self._latest_attempt(action)
        return bool(
            latest_attempt is not None
            and latest_attempt.outcome == ActionAttemptOutcome.FAILED_BEFORE_CHANGE.value
            and latest_attempt.side_effect_state
            in {
                ActionSideEffectState.NOT_ATTEMPTED.value,
                ActionSideEffectState.NONE.value,
            }
        )

    def _execution_models(
        self,
        lease: ActionExecutionLease,
    ) -> tuple[CaseActionModel, CaseActionAttemptModel]:
        action = self._session.scalar(
            select(CaseActionModel).where(CaseActionModel.id == lease.action_id).with_for_update()
        )
        attempt = self._session.scalar(
            select(CaseActionAttemptModel)
            .where(
                CaseActionAttemptModel.id == lease.attempt_id,
                CaseActionAttemptModel.action_id == lease.action_id,
            )
            .with_for_update()
        )
        if action is None or attempt is None:
            raise ActionNotFound("The action execution lease was not found.")
        return action, attempt

    def _record_receipt(
        self,
        *,
        action: CaseActionModel,
        attempt: CaseActionAttemptModel,
        receipt: ActionGatewayReceipt,
        now: datetime,
    ) -> CaseActionReceiptModel:
        existing = self._receipt(action)
        if existing is not None:
            if (
                existing.idempotency_key != receipt.idempotency_key
                or existing.external_reference != receipt.external_reference
            ):
                raise ActionConflict("A different target receipt is already bound to this action.")
            return existing
        stored = CaseActionReceiptModel(
            public_id=_stable_public_id(
                "AR",
                action.public_id,
                receipt.external_reference,
            ),
            organization_id=action.organization_id,
            case_id=action.case_id,
            action_id=action.id,
            attempt_id=attempt.id,
            legacy_external_receipt_id=None,
            provider=receipt.provider,
            external_reference=receipt.external_reference,
            idempotency_key=receipt.idempotency_key,
            status=receipt.status,
            data_fingerprint=_hash(receipt.data),
            recorded_at=now,
        )
        self._session.add(stored)
        self._session.flush()
        return stored

    def _receipt(self, action: CaseActionModel) -> CaseActionReceiptModel | None:
        return self._session.scalar(
            select(CaseActionReceiptModel).where(
                CaseActionReceiptModel.organization_id == action.organization_id,
                CaseActionReceiptModel.action_id == action.id,
            )
        )

    def _latest_attempt(
        self,
        action: CaseActionModel,
    ) -> CaseActionAttemptModel | None:
        return self._session.scalar(
            select(CaseActionAttemptModel)
            .where(
                CaseActionAttemptModel.organization_id == action.organization_id,
                CaseActionAttemptModel.action_id == action.id,
            )
            .order_by(CaseActionAttemptModel.number.desc())
            .limit(1)
        )

    def _reconcile_abandoned(
        self,
        *,
        now: datetime,
        action: CaseActionModel | None = None,
        organization_id: UUID | None = None,
    ) -> None:
        cutoff = now - timedelta(minutes=ABANDONED_ACTION_MINUTES)
        conditions = [
            CaseActionAttemptModel.outcome == ActionAttemptOutcome.RUNNING.value,
            CaseActionAttemptModel.started_at <= cutoff,
        ]
        if action is not None:
            conditions.extend(
                [
                    CaseActionAttemptModel.organization_id == action.organization_id,
                    CaseActionAttemptModel.action_id == action.id,
                ]
            )
        elif organization_id is not None:
            conditions.append(CaseActionAttemptModel.organization_id == organization_id)
        candidates = self._session.execute(
            select(
                CaseActionAttemptModel.id,
                CaseActionAttemptModel.action_id,
            )
            .where(*conditions)
            .order_by(
                CaseActionAttemptModel.action_id,
                CaseActionAttemptModel.id,
            )
        ).all()
        for attempt_id, action_id in candidates:
            target = self._session.scalar(
                select(CaseActionModel).where(CaseActionModel.id == action_id).with_for_update()
            )
            attempt = self._session.scalar(
                select(CaseActionAttemptModel)
                .where(
                    CaseActionAttemptModel.id == attempt_id,
                    CaseActionAttemptModel.outcome == ActionAttemptOutcome.RUNNING.value,
                    CaseActionAttemptModel.started_at <= cutoff,
                )
                .with_for_update()
            )
            if attempt is None:
                continue
            attempt.outcome = ActionAttemptOutcome.UNKNOWN.value
            attempt.side_effect_state = ActionSideEffectState.POSSIBLE.value
            attempt.detail = "The execution process ended before a target outcome was recorded."
            attempt.error_code = "execution_lease_abandoned"
            attempt.response_fingerprint = _hash(
                {
                    "error_code": attempt.error_code,
                    "side_effect_state": attempt.side_effect_state,
                }
            )
            attempt.finished_at = now
            if target is None or target.status != ActionStatus.RUNNING.value:
                continue
            target.status = ActionStatus.OUTCOME_UNKNOWN.value
            target.observed_outcome = attempt.detail
            target.version += 1
            target.updated_at = now
            self._add_audit(
                action=target,
                event_type="case.action_execution_abandoned",
                actor_type="system",
                actor_id="action-lease-reconciler",
                summary="An unfinished action was marked outcome unknown.",
                data={
                    "attempt_id": attempt.public_id,
                    "blind_retry_blocked": True,
                },
                correlation_id=f"action-lease:{attempt.public_id}",
                occurred_at=now,
            )

    def _advance_case_after_completion(
        self,
        action: CaseActionModel,
        *,
        now: datetime,
    ) -> None:
        case = self._session.scalar(
            select(CaseModel)
            .where(
                CaseModel.id == action.case_id,
                CaseModel.organization_id == action.organization_id,
            )
            .with_for_update()
        )
        if case is None:
            raise ActionConflict("The action case is missing.")
        if case.status != "needs_review":
            return
        case.status = "in_progress"
        case.version += 1
        case.updated_at = now

    def _required_connection(self, action: CaseActionModel) -> ConnectionModel:
        connection = self._session.get(ConnectionModel, action.connection_id)
        if connection is None or connection.organization_id != action.organization_id:
            raise ActionConflict("The action target connection is missing.")
        return connection

    def _required_review_snapshot(
        self,
        review: CaseReviewModel,
    ) -> CaseReviewSnapshotModel:
        snapshot = self._session.scalar(
            select(CaseReviewSnapshotModel).where(
                CaseReviewSnapshotModel.organization_id == review.organization_id,
                CaseReviewSnapshotModel.case_id == review.case_id,
                CaseReviewSnapshotModel.review_id == review.id,
            )
        )
        if snapshot is None:
            raise ActionConflict("The immutable review snapshot is missing.")
        return snapshot

    def _required_action(
        self,
        organization_public_id: str,
        action_public_id: str,
        *,
        for_update: bool = False,
    ) -> CaseActionModel:
        action = self._scoped_action(
            organization_public_id,
            action_public_id,
            for_update=for_update,
        )
        if action is None:
            raise ActionNotFound("The action was not found.")
        return action

    def _scoped_action(
        self,
        organization_public_id: str,
        action_public_id: str,
        *,
        for_update: bool = False,
    ) -> CaseActionModel | None:
        statement = (
            select(CaseActionModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == CaseActionModel.organization_id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseActionModel.public_id == action_public_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _organization(self, organization_public_id: str) -> OrganizationModel | None:
        return self._session.scalar(
            select(OrganizationModel).where(OrganizationModel.public_id == organization_public_id)
        )

    def _active_member(
        self,
        *,
        organization_id: UUID,
        actor_id: str,
    ) -> MembershipModel:
        member = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization_id,
                MembershipModel.status == "active",
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        )
        if member is None:
            raise ActorMembershipNotFound(
                "An active organization membership is required for this action."
            )
        return member

    def _add_audit(
        self,
        *,
        action: CaseActionModel,
        event_type: str,
        actor_type: str,
        actor_id: str,
        summary: str,
        data: dict[str, object],
        correlation_id: str,
        occurred_at: datetime,
    ) -> None:
        self._session.add(
            AuditEventModel(
                organization_id=action.organization_id,
                task_id=None,
                run_id=None,
                event_type=event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                subject_type="action",
                subject_id=action.public_id,
                summary=summary,
                data=data,
                correlation_id=correlation_id,
                occurred_at=occurred_at,
            )
        )


def _materialization_blocker(
    *,
    execution_eligible: bool,
    connection: ConnectionModel,
    now: datetime,
) -> ActionExecutionBlocker | None:
    if not execution_eligible:
        return ActionExecutionBlocker.STALE_PROPOSAL
    if not _connection_is_eligible(connection, now=now):
        return ActionExecutionBlocker.CONNECTION_UNAVAILABLE
    return None


def _connection_is_eligible(
    connection: ConnectionModel,
    *,
    now: datetime,
) -> bool:
    return bool(
        connection.health == ConnectionHealth.HEALTHY.value
        and connection.credential_status not in {"missing", "expired"}
        and connection.adapter_key != "unconfigured"
        and connection.last_checked_at is not None
        and connection.last_checked_at > now - timedelta(minutes=CONNECTION_HEALTH_MAX_AGE_MINUTES)
    )


def _action_target(
    proposed_action: CaseProposedActionModel,
    case: CaseModel,
) -> str:
    for key in (
        "external_reference",
        "payment_id",
        "invoice_id",
        "account_id",
        "order_id",
        "case_id",
    ):
        value = proposed_action.parameters.get(key)
        if value:
            return value
    return case.external_reference or case.public_id


def _blocker_message(blocker: ActionExecutionBlocker) -> str:
    return {
        ActionExecutionBlocker.PERMISSION: (
            "Your role does not have permission to execute this action."
        ),
        ActionExecutionBlocker.DUPLICATE: (
            "This action already has a target receipt and cannot be repeated."
        ),
        ActionExecutionBlocker.EXPIRED_APPROVAL: (
            "The approval expired. Submit the current resolution for review again."
        ),
        ActionExecutionBlocker.CONNECTION_UNAVAILABLE: (
            "The target connection is not healthy and configured for this action."
        ),
        ActionExecutionBlocker.STALE_PROPOSAL: (
            "The approved resolution no longer matches the current case."
        ),
    }[blocker]


def _stable_public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _encode_cursor(
    updated_at: datetime,
    public_id: str,
    filter_fingerprint: str,
) -> str:
    payload = json.dumps(
        {
            "updated_at": updated_at.astimezone(UTC).isoformat(),
            "public_id": public_id,
            "filter": filter_fingerprint,
        },
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str, expected_filter: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        updated_at = datetime.fromisoformat(payload["updated_at"])
        public_id = str(payload["public_id"])
        filter_fingerprint = str(payload["filter"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidActionCursor("The action cursor is invalid.") from exc
    if updated_at.tzinfo is None or filter_fingerprint != expected_filter:
        raise InvalidActionCursor("The action cursor does not match these filters.")
    return updated_at.astimezone(UTC), public_id
