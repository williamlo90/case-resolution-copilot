from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.inbox import (
    CaseDraftContext,
    DraftDeliveryRecord,
    DraftDeliveryStatus,
    DraftReceipt,
    InboxConflict,
    InboxNotFound,
    InboxReplyContext,
    ReviewDraftAuthorization,
)
from app.persistence.models import (
    CaseModel,
    ConnectionModel,
    ExternalConversationModel,
    ExternalMessageModel,
    InboxDraftDeliveryModel,
    OrganizationModel,
    utc_now,
)

from ._base import InboxRepositoryBase
from .draft_fingerprint import draft_delivery_key


class InboxDraftRepository(InboxRepositoryBase):
    def reply_context(
        self,
        *,
        organization_public_id: str,
        case_id: UUID,
    ) -> InboxReplyContext:
        row = self._session.execute(
            select(ExternalConversationModel, ConnectionModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == ExternalConversationModel.organization_id,
            )
            .join(
                ConnectionModel,
                (ConnectionModel.organization_id == ExternalConversationModel.organization_id)
                & (ConnectionModel.id == ExternalConversationModel.connection_id),
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                ExternalConversationModel.case_id == case_id,
            )
        ).one_or_none()
        if row is None:
            raise InboxNotFound("This case is not linked to a connected inbox thread.")
        conversation, connection = row
        if (
            connection.credential_status != "connected"
            or "draft_create" not in connection.write_capabilities
        ):
            raise InboxConflict("Connect the inbox with draft access before continuing.")
        messages = list(
            self._session.scalars(
                select(ExternalMessageModel)
                .where(
                    ExternalMessageModel.organization_id == conversation.organization_id,
                    ExternalMessageModel.external_conversation_id == conversation.id,
                )
                .order_by(
                    ExternalMessageModel.provider_received_at,
                    ExternalMessageModel.provider_message_id,
                )
            )
        )
        inbound = [item for item in messages if item.direction == "inbound"]
        if not inbound:
            raise InboxConflict("The conversation has no customer message to reply to.")
        latest = inbound[-1]
        recipient = latest.sender.get("address")
        if not isinstance(recipient, str) or "@" not in recipient:
            raise InboxConflict("The customer reply address is unavailable.")
        references = tuple(
            item.rfc_message_id for item in messages if item.rfc_message_id
        )[-50:]
        return InboxReplyContext(
            external_conversation_id=conversation.id,
            connection_id=connection.id,
            connection_public_id=connection.public_id,
            provider_thread_id=conversation.provider_thread_id,
            recipient=recipient,
            in_reply_to=latest.rfc_message_id,
            references=references,
            conversation_fingerprint=conversation.source_fingerprint,
        )

    def prepare(
        self,
        *,
        organization_id: UUID,
        case: CaseDraftContext,
        reply: InboxReplyContext,
        review: ReviewDraftAuthorization,
    ) -> DraftDeliveryRecord:
        idempotency_key = draft_delivery_key(
            organization_id=organization_id,
            case=case,
            reply=reply,
            review=review,
        )
        existing = self._session.scalar(
            select(InboxDraftDeliveryModel).where(
                InboxDraftDeliveryModel.organization_id == organization_id,
                InboxDraftDeliveryModel.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return DraftDeliveryRecord.model_validate(existing)
        now = utc_now()
        model = InboxDraftDeliveryModel(
            public_id=f"IDL-{uuid4().hex[:12].upper()}",
            organization_id=organization_id,
            case_id=case.case_id,
            external_conversation_id=reply.external_conversation_id,
            connection_id=reply.connection_id,
            response_draft_id=case.response_draft_id,
            response_draft_version=case.response_draft_version,
            review_id=review.review_id,
            decision_fingerprint=review.snapshot_fingerprint,
            evidence_fingerprint=review.evidence_fingerprint,
            policy_fingerprint=review.policy_fingerprint,
            conversation_fingerprint=reply.conversation_fingerprint,
            response_fingerprint=case.response_fingerprint,
            provider_thread_id=reply.provider_thread_id,
            recipient=reply.recipient,
            subject_snapshot=case.subject,
            body_hash=sha256(case.body.encode("utf-8")).hexdigest(),
            in_reply_to=reply.in_reply_to,
            references=list(reply.references),
            idempotency_key=idempotency_key,
            status=DraftDeliveryStatus.READY.value,
            provider_draft_id=None,
            provider_message_id=None,
            attempt_count=0,
            lease_owner=None,
            lease_expires_at=None,
            last_error_code=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        self._session.flush()
        return DraftDeliveryRecord.model_validate(model)

    def start(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        worker_id: str,
    ) -> DraftDeliveryRecord:
        delivery = self._required(organization_id, delivery_id, for_update=True)
        if delivery.status == DraftDeliveryStatus.COMPLETED.value:
            return DraftDeliveryRecord.model_validate(delivery)
        if delivery.status not in {
            DraftDeliveryStatus.READY.value,
            DraftDeliveryStatus.FAILED_SAFE.value,
        }:
            raise InboxConflict("Check the existing draft result before trying again.")
        now = utc_now()
        delivery.status = DraftDeliveryStatus.RUNNING.value
        delivery.attempt_count += 1
        delivery.lease_owner = worker_id
        delivery.lease_expires_at = now + timedelta(seconds=60)
        delivery.updated_at = now
        self._session.flush()
        return DraftDeliveryRecord.model_validate(delivery)

    def complete(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        receipt: DraftReceipt,
        expected_worker_id: str | None,
    ) -> DraftDeliveryRecord:
        delivery = self._required(organization_id, delivery_id, for_update=True)
        if delivery.status == DraftDeliveryStatus.COMPLETED.value:
            return DraftDeliveryRecord.model_validate(delivery)
        self._require_transition_owner(delivery, expected_worker_id)
        delivery.status = DraftDeliveryStatus.COMPLETED.value
        delivery.provider_draft_id = receipt.provider_draft_id
        delivery.provider_message_id = receipt.provider_message_id
        delivery.lease_owner = None
        delivery.lease_expires_at = None
        delivery.last_error_code = None
        delivery.completed_at = utc_now()
        delivery.updated_at = utc_now()
        self._session.flush()
        return DraftDeliveryRecord.model_validate(delivery)

    def record_failure(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        status: DraftDeliveryStatus,
        error_code: str,
        expected_worker_id: str | None,
    ) -> DraftDeliveryRecord:
        delivery = self._required(organization_id, delivery_id, for_update=True)
        self._require_transition_owner(delivery, expected_worker_id)
        delivery.status = status.value
        delivery.lease_owner = None
        delivery.lease_expires_at = None
        delivery.last_error_code = error_code[:100]
        delivery.updated_at = utc_now()
        self._session.flush()
        return DraftDeliveryRecord.model_validate(delivery)

    def get(
        self,
        *,
        organization_public_id: str,
        delivery_public_id: str,
    ) -> DraftDeliveryRecord:
        delivery = self._session.scalar(
            select(InboxDraftDeliveryModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == InboxDraftDeliveryModel.organization_id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                InboxDraftDeliveryModel.public_id == delivery_public_id,
            )
        )
        if delivery is None:
            raise InboxNotFound("The draft delivery was not found.")
        return DraftDeliveryRecord.model_validate(delivery)

    def latest_for_case(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        expected_draft_version: int,
    ) -> DraftDeliveryRecord | None:
        delivery = self._session.scalar(
            select(InboxDraftDeliveryModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == InboxDraftDeliveryModel.organization_id,
            )
            .join(
                CaseModel,
                (CaseModel.organization_id == InboxDraftDeliveryModel.organization_id)
                & (CaseModel.id == InboxDraftDeliveryModel.case_id),
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
                InboxDraftDeliveryModel.response_draft_version
                == expected_draft_version,
            )
            .order_by(
                InboxDraftDeliveryModel.updated_at.desc(),
                InboxDraftDeliveryModel.id.desc(),
            )
            .limit(1)
        )
        return (
            DraftDeliveryRecord.model_validate(delivery)
            if delivery is not None
            else None
        )

    def _required(
        self,
        organization_id: UUID,
        delivery_id: UUID,
        *,
        for_update: bool,
    ) -> InboxDraftDeliveryModel:
        statement = select(InboxDraftDeliveryModel).where(
            InboxDraftDeliveryModel.organization_id == organization_id,
            InboxDraftDeliveryModel.id == delivery_id,
        )
        if for_update:
            statement = statement.with_for_update()
        delivery = self._session.scalar(statement)
        if delivery is None:
            raise InboxNotFound("The draft delivery was not found.")
        return delivery

    @staticmethod
    def _require_transition_owner(
        delivery: InboxDraftDeliveryModel,
        expected_worker_id: str | None,
    ) -> None:
        if expected_worker_id is not None:
            if (
                delivery.status != DraftDeliveryStatus.RUNNING.value
                or delivery.lease_owner != expected_worker_id
            ):
                raise InboxConflict("The draft delivery is owned by another worker.")
            return
        if delivery.status in {
            DraftDeliveryStatus.OUTCOME_UNKNOWN.value,
            DraftDeliveryStatus.RECOVERY_REQUIRED.value,
        }:
            return
        if (
            delivery.status == DraftDeliveryStatus.RUNNING.value
            and delivery.lease_expires_at is not None
            and delivery.lease_expires_at <= utc_now()
        ):
            return
        raise InboxConflict("The draft delivery is not ready for reconciliation.")
