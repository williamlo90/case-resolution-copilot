from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.identity import ActorContext, Permission
from app.domain.inbox import (
    CreateDraftRequest,
    DraftDeliveryRecord,
    DraftDeliveryResult,
    DraftDeliveryStatus,
    DraftLookupStatus,
    FindDraftRequest,
    InboxAuthorizationError,
    InboxConflict,
    InboxProviderUnavailable,
)
from app.ports.inbox import InboxDraftGatewayResolver
from app.ports.inbox_access import InboxAccessProvider
from app.ports.inbox_draft_persistence import InboxDraftUnitOfWorkFactory
from app.security.authorization import require_permission


class InboxDraftDeliveryService:
    def __init__(
        self,
        *,
        unit_of_work: InboxDraftUnitOfWorkFactory,
        gateways: InboxDraftGatewayResolver,
        access: InboxAccessProvider,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._gateways = gateways
        self._access = access

    def latest(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_draft_version: int,
    ) -> DraftDeliveryRecord | None:
        require_permission(actor, Permission.CASE_READ)
        with self._unit_of_work() as uow:
            return uow.deliveries.latest_for_case(
                organization_public_id=actor.organization_id,
                case_public_id=case_id,
                expected_draft_version=expected_draft_version,
            )

    def deliver(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_draft_version: int,
        worker_id: str,
    ) -> DraftDeliveryResult:
        require_permission(actor, Permission.CASE_MANAGE)
        with self._unit_of_work() as uow:
            case = uow.cases.current(
                organization_public_id=actor.organization_id,
                case_public_id=case_id,
                expected_draft_version=expected_draft_version,
            )
            review = uow.reviews.current_approval(
                organization_public_id=actor.organization_id,
                case_public_id=case_id,
            )
            reply = uow.deliveries.reply_context(
                organization_public_id=actor.organization_id,
                case_id=case.case_id,
            )
            delivery = uow.deliveries.prepare(
                organization_id=case.organization_id,
                case=case,
                reply=reply,
                review=review,
            )
            delivery = uow.deliveries.start(
                organization_id=case.organization_id,
                delivery_id=delivery.id,
                worker_id=worker_id,
            )
        if delivery.status is DraftDeliveryStatus.COMPLETED:
            return DraftDeliveryResult(delivery=delivery)

        try:
            access = self._access.access(
                organization_id=actor.organization_id,
                connection_id=reply.connection_public_id,
            )
        except (InboxAuthorizationError, InboxProviderUnavailable):
            return DraftDeliveryResult(
                delivery=self._failure(
                    organization_id=delivery.organization_id,
                    delivery=delivery,
                    status=DraftDeliveryStatus.FAILED_SAFE,
                    error_code="access_unavailable",
                    expected_worker_id=worker_id,
                )
            )
        request = CreateDraftRequest(
            provider_thread_id=reply.provider_thread_id,
            recipient=reply.recipient,
            subject=case.subject,
            body=case.body,
            in_reply_to=reply.in_reply_to,
            references=reply.references,
            correlation_key=delivery.idempotency_key,
        )
        try:
            receipt = self._gateways.drafts(access.adapter_key).create_reply_draft(
                access=access.access,
                request=request,
            )
        except (InboxAuthorizationError, InboxProviderUnavailable):
            return DraftDeliveryResult(
                delivery=self._failure(
                    organization_id=delivery.organization_id,
                    delivery=delivery,
                    status=DraftDeliveryStatus.OUTCOME_UNKNOWN,
                    error_code="provider_outcome_unknown",
                    expected_worker_id=worker_id,
                )
            )
        with self._unit_of_work() as uow:
            completed = uow.deliveries.complete(
                organization_id=delivery.organization_id,
                delivery_id=delivery.id,
                receipt=receipt,
                expected_worker_id=worker_id,
            )
        return DraftDeliveryResult(delivery=completed)

    def reconcile(
        self,
        *,
        actor: ActorContext,
        delivery_id: str,
    ) -> DraftDeliveryResult:
        require_permission(actor, Permission.CASE_MANAGE)
        with self._unit_of_work() as uow:
            delivery = uow.deliveries.get(
                organization_public_id=actor.organization_id,
                delivery_public_id=delivery_id,
            )
        if delivery.status is DraftDeliveryStatus.COMPLETED:
            return DraftDeliveryResult(delivery=delivery)
        if (
            delivery.status is DraftDeliveryStatus.RUNNING
            and (
                delivery.lease_expires_at is None
                or delivery.lease_expires_at > datetime.now(UTC)
            )
        ):
            raise InboxConflict("Draft creation is still in progress.")
        if delivery.status not in {
            DraftDeliveryStatus.RUNNING,
            DraftDeliveryStatus.OUTCOME_UNKNOWN,
            DraftDeliveryStatus.RECOVERY_REQUIRED,
        }:
            raise InboxConflict("This draft delivery does not need reconciliation.")
        try:
            access = self._access.access(
                organization_id=actor.organization_id,
                connection_id=self._connection_public_id(
                    actor=actor,
                    case_id=delivery.case_id,
                ),
            )
            lookup = self._gateways.drafts(access.adapter_key).find_draft(
                access=access.access,
                request=FindDraftRequest(
                    provider_thread_id=delivery.provider_thread_id,
                    correlation_key=delivery.idempotency_key,
                    recipient=delivery.recipient,
                    subject=delivery.subject_snapshot,
                    body_hash=delivery.body_hash,
                    not_before=delivery.created_at - timedelta(minutes=1),
                ),
            )
        except (InboxAuthorizationError, InboxProviderUnavailable):
            return DraftDeliveryResult(
                delivery=self._failure(
                    organization_id=delivery.organization_id,
                    delivery=delivery,
                    status=DraftDeliveryStatus.RECOVERY_REQUIRED,
                    error_code="reconciliation_unavailable",
                    expected_worker_id=None,
                )
            )
        if lookup.status is DraftLookupStatus.FOUND and lookup.receipt is not None:
            with self._unit_of_work() as uow:
                completed = uow.deliveries.complete(
                    organization_id=delivery.organization_id,
                    delivery_id=delivery.id,
                    receipt=lookup.receipt,
                    expected_worker_id=None,
                )
            return DraftDeliveryResult(delivery=completed)
        status = (
            DraftDeliveryStatus.FAILED_SAFE
            if lookup.status is DraftLookupStatus.ABSENT and lookup.absence_is_terminal
            else DraftDeliveryStatus.RECOVERY_REQUIRED
        )
        return DraftDeliveryResult(
            delivery=self._failure(
                organization_id=delivery.organization_id,
                delivery=delivery,
                status=status,
                error_code=f"reconciliation_{lookup.status.value}",
                expected_worker_id=None,
            )
        )

    def _connection_public_id(self, *, actor: ActorContext, case_id: UUID) -> str:
        with self._unit_of_work() as uow:
            reply = uow.deliveries.reply_context(
                organization_public_id=actor.organization_id,
                case_id=case_id,
            )
        return reply.connection_public_id

    def _failure(
        self,
        *,
        organization_id: UUID,
        delivery: DraftDeliveryRecord,
        status: DraftDeliveryStatus,
        error_code: str,
        expected_worker_id: str | None,
    ) -> DraftDeliveryRecord:
        with self._unit_of_work() as uow:
            return uow.deliveries.record_failure(
                organization_id=organization_id,
                delivery_id=delivery.id,
                status=status,
                error_code=error_code,
                expected_worker_id=expected_worker_id,
            )
