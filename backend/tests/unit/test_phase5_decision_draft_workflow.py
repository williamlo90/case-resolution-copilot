from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from app.domain.inbox import (
    AccessCredential,
    CaseDraftContext,
    CreateDraftRequest,
    DraftDeliveryRecord,
    DraftDeliveryStatus,
    DraftLookupResult,
    DraftLookupStatus,
    DraftReceipt,
    FindDraftRequest,
    InboxAccessContext,
    InboxConflict,
    InboxNotFound,
    InboxProviderUnavailable,
    InboxReplyContext,
    ReviewDraftAuthorization,
)
from app.domain.reviews import ReviewSnapshotStale
from app.persistence.inbox.draft_fingerprint import draft_delivery_key
from app.ports.inbox_draft_persistence import (
    CaseDraftStore,
    InboxDraftStore,
    InboxDraftUnitOfWork,
    ReviewDraftAuthorizationStore,
)
from app.security.authentication import DeterministicAuthProvider
from app.security.authorization import PermissionDenied
from app.services.inbox.draft_delivery import InboxDraftDeliveryService

NOW = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)
ORGANIZATION_ID = uuid5(NAMESPACE_URL, "phase-5:organization")
CASE_ID = uuid5(NAMESPACE_URL, "phase-5:case")
CONVERSATION_ID = uuid5(NAMESPACE_URL, "phase-5:conversation")
CONNECTION_ID = uuid5(NAMESPACE_URL, "phase-5:connection")
DRAFT_ID = uuid5(NAMESPACE_URL, "phase-5:response-draft")
REVIEW_ID = uuid5(NAMESPACE_URL, "phase-5:review")


def _case_context() -> CaseDraftContext:
    return CaseDraftContext(
        organization_id=ORGANIZATION_ID,
        case_id=CASE_ID,
        case_public_id="CS-2047",
        case_version=3,
        response_draft_id=DRAFT_ID,
        response_draft_version=2,
        subject="Re: Duplicate charge on INV-78412",
        body=(
            "We verified the duplicate charge. The proposed correction remains pending "
            "supervisor approval."
        ),
        response_fingerprint="r" * 64,
        response_content_fingerprint="m" * 64,
    )


def _review_authorization() -> ReviewDraftAuthorization:
    return ReviewDraftAuthorization(
        review_id=REVIEW_ID,
        snapshot_fingerprint="d" * 64,
        evidence_fingerprint="e" * 64,
        policy_fingerprint="p" * 64,
        response_content_fingerprint="m" * 64,
    )


def _reply_context() -> InboxReplyContext:
    return InboxReplyContext(
        external_conversation_id=CONVERSATION_ID,
        connection_id=CONNECTION_ID,
        connection_public_id="CON-INBOX-001",
        provider_thread_id="thread-billing-001",
        recipient="nadia@example.com",
        in_reply_to="<msg-001@example.com>",
        references=("<msg-001@example.com>",),
        conversation_fingerprint="c" * 64,
    )


@dataclass
class _WorkflowState:
    case: CaseDraftContext
    review: ReviewDraftAuthorization
    reply: InboxReplyContext
    delivery: DraftDeliveryRecord | None = None
    approval_is_stale: bool = False


class _CaseStore:
    def __init__(self, state: _WorkflowState) -> None:
        self._state = state

    def current(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        expected_draft_version: int,
    ) -> CaseDraftContext:
        if organization_public_id != "ORG-0001" or case_public_id != "CS-2047":
            raise InboxNotFound("The response draft was not found.")
        if expected_draft_version != self._state.case.response_draft_version:
            raise InboxConflict("The response draft changed.")
        return self._state.case


class _ReviewStore:
    def __init__(self, state: _WorkflowState) -> None:
        self._state = state

    def current_approval(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> ReviewDraftAuthorization:
        assert organization_public_id == "ORG-0001"
        assert case_public_id == "CS-2047"
        if self._state.approval_is_stale:
            raise ReviewSnapshotStale("The approved review no longer matches the case.")
        return self._state.review


class _DeliveryStore:
    def __init__(self, state: _WorkflowState) -> None:
        self._state = state

    def reply_context(
        self,
        *,
        organization_public_id: str,
        case_id: UUID,
    ) -> InboxReplyContext:
        assert organization_public_id == "ORG-0001"
        assert case_id == CASE_ID
        return self._state.reply

    def prepare(
        self,
        *,
        organization_id: UUID,
        case: CaseDraftContext,
        reply: InboxReplyContext,
        review: ReviewDraftAuthorization,
    ) -> DraftDeliveryRecord:
        key = draft_delivery_key(
            organization_id=organization_id,
            case=case,
            reply=reply,
            review=review,
        )
        if self._state.delivery is not None:
            assert self._state.delivery.idempotency_key == key
            return self._state.delivery
        self._state.delivery = DraftDeliveryRecord(
            id=uuid5(NAMESPACE_URL, "phase-5:delivery"),
            public_id="IDL-PHASE5-001",
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
            body_hash="b" * 64,
            in_reply_to=reply.in_reply_to,
            references=list(reply.references),
            idempotency_key=key,
            status=DraftDeliveryStatus.READY,
            provider_draft_id=None,
            provider_message_id=None,
            attempt_count=0,
            lease_owner=None,
            lease_expires_at=None,
            last_error_code=None,
            completed_at=None,
            created_at=NOW,
            updated_at=NOW,
        )
        return self._state.delivery

    def start(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        worker_id: str,
    ) -> DraftDeliveryRecord:
        delivery = self._required(organization_id, delivery_id)
        if delivery.status is DraftDeliveryStatus.COMPLETED:
            return delivery
        if delivery.status not in {
            DraftDeliveryStatus.READY,
            DraftDeliveryStatus.FAILED_SAFE,
        }:
            raise InboxConflict("Check the existing draft result before trying again.")
        self._state.delivery = delivery.model_copy(
            update={
                "status": DraftDeliveryStatus.RUNNING,
                "attempt_count": delivery.attempt_count + 1,
                "lease_owner": worker_id,
                "lease_expires_at": NOW + timedelta(minutes=1),
                "updated_at": NOW,
            }
        )
        return self._state.delivery

    def complete(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        receipt: DraftReceipt,
        expected_worker_id: str | None,
    ) -> DraftDeliveryRecord:
        delivery = self._required(organization_id, delivery_id)
        if delivery.status is DraftDeliveryStatus.COMPLETED:
            return delivery
        if expected_worker_id is not None:
            assert delivery.lease_owner == expected_worker_id
        self._state.delivery = delivery.model_copy(
            update={
                "status": DraftDeliveryStatus.COMPLETED,
                "provider_draft_id": receipt.provider_draft_id,
                "provider_message_id": receipt.provider_message_id,
                "lease_owner": None,
                "lease_expires_at": None,
                "last_error_code": None,
                "completed_at": NOW,
                "updated_at": NOW,
            }
        )
        return self._state.delivery

    def record_failure(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        status: DraftDeliveryStatus,
        error_code: str,
        expected_worker_id: str | None,
    ) -> DraftDeliveryRecord:
        delivery = self._required(organization_id, delivery_id)
        if expected_worker_id is not None:
            assert delivery.lease_owner == expected_worker_id
        self._state.delivery = delivery.model_copy(
            update={
                "status": status,
                "lease_owner": None,
                "lease_expires_at": None,
                "last_error_code": error_code,
                "updated_at": NOW,
            }
        )
        return self._state.delivery

    def get(
        self,
        *,
        organization_public_id: str,
        delivery_public_id: str,
    ) -> DraftDeliveryRecord:
        assert organization_public_id == "ORG-0001"
        delivery = self._state.delivery
        if delivery is None or delivery.public_id != delivery_public_id:
            raise InboxNotFound("The draft delivery was not found.")
        return delivery

    def latest_for_case(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        expected_draft_version: int,
    ) -> DraftDeliveryRecord | None:
        assert organization_public_id == "ORG-0001"
        assert case_public_id == "CS-2047"
        delivery = self._state.delivery
        if delivery is None or delivery.response_draft_version != expected_draft_version:
            return None
        return delivery

    def _required(self, organization_id: UUID, delivery_id: UUID) -> DraftDeliveryRecord:
        delivery = self._state.delivery
        if (
            delivery is None
            or delivery.organization_id != organization_id
            or delivery.id != delivery_id
        ):
            raise InboxNotFound("The draft delivery was not found.")
        return delivery


class _DraftUnitOfWork:
    def __init__(self, state: _WorkflowState) -> None:
        self.cases: CaseDraftStore = _CaseStore(state)
        self.reviews: ReviewDraftAuthorizationStore = _ReviewStore(state)
        self.deliveries: InboxDraftStore = _DeliveryStore(state)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        del exc_type, exc_value, traceback
        return None


class _UnitOfWorkFactory:
    def __init__(self, state: _WorkflowState) -> None:
        self._state = state
        self.calls = 0

    def __call__(self) -> InboxDraftUnitOfWork:
        self.calls += 1
        return _DraftUnitOfWork(self._state)


class _CountingDraftGateway:
    provider_name = "deterministic"

    def __init__(self, *, fail_after_create: bool = False) -> None:
        self.fail_after_create = fail_after_create
        self.create_calls = 0
        self.lookup_calls = 0
        self._receipts: dict[str, DraftReceipt] = {}

    def create_reply_draft(
        self,
        *,
        access: AccessCredential,
        request: CreateDraftRequest,
    ) -> DraftReceipt:
        assert access.access_token.get_secret_value() == "phase-5-access"
        self.create_calls += 1
        receipt = DraftReceipt(
            provider_draft_id="gmail-draft-phase-5",
            provider_message_id="gmail-message-phase-5",
            provider_thread_id=request.provider_thread_id,
            created_at=NOW,
        )
        self._receipts[request.correlation_key] = receipt
        if self.fail_after_create:
            raise InboxProviderUnavailable("The provider outcome is unknown.")
        return receipt

    def find_draft(
        self,
        *,
        access: AccessCredential,
        request: FindDraftRequest,
    ) -> DraftLookupResult:
        assert access.access_token.get_secret_value() == "phase-5-access"
        self.lookup_calls += 1
        receipt = self._receipts.get(request.correlation_key)
        return DraftLookupResult(
            status=(DraftLookupStatus.FOUND if receipt else DraftLookupStatus.ABSENT),
            receipt=receipt,
            absence_is_terminal=receipt is None,
        )


class _GatewayResolver:
    def __init__(self, gateway: _CountingDraftGateway) -> None:
        self._gateway = gateway

    def drafts(self, adapter_key: str) -> _CountingDraftGateway:
        assert adapter_key == "deterministic_inbox"
        return self._gateway


class _AccessProvider:
    def __init__(self) -> None:
        self.calls = 0

    def access(
        self,
        *,
        organization_id: str,
        connection_id: str,
    ) -> InboxAccessContext:
        assert organization_id == "ORG-0001"
        assert connection_id == "CON-INBOX-001"
        self.calls += 1
        return InboxAccessContext(
            organization_id=ORGANIZATION_ID,
            connection_id=CONNECTION_ID,
            connection_public_id=connection_id,
            adapter_key="deterministic_inbox",
            account_address="pilot-inbox@example.com",
            import_mode="manual",
            access=AccessCredential(
                access_token="phase-5-access",
                expires_at=NOW + timedelta(hours=1),
            ),
        )


def _workflow(
    *,
    approval_is_stale: bool = False,
    fail_after_create: bool = False,
    approved_response_matches: bool = True,
) -> tuple[
    InboxDraftDeliveryService,
    _WorkflowState,
    _CountingDraftGateway,
    _AccessProvider,
    _UnitOfWorkFactory,
]:
    state = _WorkflowState(
        case=_case_context(),
        review=_review_authorization().model_copy(
            update=(
                {}
                if approved_response_matches
                else {"response_content_fingerprint": "x" * 64}
            )
        ),
        reply=_reply_context(),
        approval_is_stale=approval_is_stale,
    )
    factory = _UnitOfWorkFactory(state)
    gateway = _CountingDraftGateway(fail_after_create=fail_after_create)
    access = _AccessProvider()
    service = InboxDraftDeliveryService(
        unit_of_work=factory,
        gateways=_GatewayResolver(gateway),
        access=access,
    )
    return service, state, gateway, access, factory


def _deliver(service: InboxDraftDeliveryService) -> DraftDeliveryRecord:
    result = service.deliver(
        actor=DeterministicAuthProvider().authenticate("USR-0001"),
        case_id="CS-2047",
        expected_draft_version=2,
        worker_id="phase-5-worker",
    )
    return result.delivery


def test_approved_draft_replay_creates_exactly_one_provider_draft() -> None:
    service, _, gateway, access, _ = _workflow()

    first = _deliver(service)
    replay = _deliver(service)

    assert first.status is DraftDeliveryStatus.COMPLETED
    assert replay == first
    assert gateway.create_calls == 1
    assert access.calls == 1
    assert first.decision_fingerprint == "d" * 64
    assert first.evidence_fingerprint == "e" * 64
    assert first.policy_fingerprint == "p" * 64
    assert first.conversation_fingerprint == "c" * 64
    assert first.response_fingerprint == "r" * 64


def test_stale_approval_is_rejected_before_any_provider_access() -> None:
    service, state, gateway, access, _ = _workflow(approval_is_stale=True)

    with pytest.raises(ReviewSnapshotStale, match="no longer matches"):
        _deliver(service)

    assert state.delivery is None
    assert gateway.create_calls == 0
    assert access.calls == 0


def test_draft_changed_after_approval_is_rejected_before_provider_access() -> None:
    service, state, gateway, access, _ = _workflow(
        approved_response_matches=False
    )

    with pytest.raises(ReviewSnapshotStale, match="changed after approval"):
        _deliver(service)

    assert state.delivery is None
    assert gateway.create_calls == 0
    assert access.calls == 0


def test_unknown_provider_outcome_reconciles_without_replaying_the_write() -> None:
    service, _, gateway, _, _ = _workflow(fail_after_create=True)

    uncertain = _deliver(service)
    assert uncertain.status is DraftDeliveryStatus.OUTCOME_UNKNOWN

    reconciled = service.reconcile(
        actor=DeterministicAuthProvider().authenticate("USR-0001"),
        delivery_id=uncertain.public_id,
    ).delivery
    replay = _deliver(service)

    assert reconciled.status is DraftDeliveryStatus.COMPLETED
    assert replay == reconciled
    assert gateway.create_calls == 1
    assert gateway.lookup_calls == 1


def test_auditor_cannot_start_draft_delivery() -> None:
    service, state, gateway, access, factory = _workflow()

    with pytest.raises(PermissionDenied):
        service.deliver(
            actor=DeterministicAuthProvider().authenticate("USR-0004"),
            case_id="CS-2047",
            expected_draft_version=2,
            worker_id="phase-5-worker",
        )

    assert factory.calls == 0
    assert state.delivery is None
    assert gateway.create_calls == 0
    assert access.calls == 0


def test_draft_idempotency_key_binds_every_authorized_snapshot() -> None:
    case = _case_context()
    reply = _reply_context()
    review = _review_authorization()
    baseline = draft_delivery_key(
        organization_id=ORGANIZATION_ID,
        case=case,
        reply=reply,
        review=review,
    )
    changed_keys = {
        draft_delivery_key(
            organization_id=ORGANIZATION_ID,
            case=case,
            reply=reply,
            review=review.model_copy(update={"snapshot_fingerprint": "s" * 64}),
        ),
        draft_delivery_key(
            organization_id=ORGANIZATION_ID,
            case=case,
            reply=reply,
            review=review.model_copy(update={"evidence_fingerprint": "f" * 64}),
        ),
        draft_delivery_key(
            organization_id=ORGANIZATION_ID,
            case=case,
            reply=reply,
            review=review.model_copy(update={"policy_fingerprint": "q" * 64}),
        ),
        draft_delivery_key(
            organization_id=ORGANIZATION_ID,
            case=case,
            reply=reply.model_copy(update={"conversation_fingerprint": "v" * 64}),
            review=review,
        ),
        draft_delivery_key(
            organization_id=ORGANIZATION_ID,
            case=case.model_copy(update={"response_fingerprint": "w" * 64}),
            reply=reply,
            review=review,
        ),
    }

    assert len(baseline) == 64
    assert len(changed_keys) == 5
    assert baseline not in changed_keys
