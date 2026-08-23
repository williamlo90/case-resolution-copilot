from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.domain.inbox import (
    CaseDraftContext,
    DraftDeliveryRecord,
    DraftDeliveryStatus,
    DraftReceipt,
    InboxReplyContext,
    ReviewDraftAuthorization,
)


class CaseDraftStore(Protocol):
    def current(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        expected_draft_version: int,
    ) -> CaseDraftContext: ...


class ReviewDraftAuthorizationStore(Protocol):
    def current_approval(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> ReviewDraftAuthorization: ...


class InboxDraftStore(Protocol):
    def reply_context(
        self,
        *,
        organization_public_id: str,
        case_id: UUID,
    ) -> InboxReplyContext: ...

    def prepare(
        self,
        *,
        organization_id: UUID,
        case: CaseDraftContext,
        reply: InboxReplyContext,
        review: ReviewDraftAuthorization,
    ) -> DraftDeliveryRecord: ...

    def start(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        worker_id: str,
    ) -> DraftDeliveryRecord: ...

    def complete(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        receipt: DraftReceipt,
        expected_worker_id: str | None,
    ) -> DraftDeliveryRecord: ...

    def record_failure(
        self,
        *,
        organization_id: UUID,
        delivery_id: UUID,
        status: DraftDeliveryStatus,
        error_code: str,
        expected_worker_id: str | None,
    ) -> DraftDeliveryRecord: ...

    def get(
        self,
        *,
        organization_public_id: str,
        delivery_public_id: str,
    ) -> DraftDeliveryRecord: ...

    def latest_for_case(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        expected_draft_version: int,
    ) -> DraftDeliveryRecord | None: ...


class InboxDraftUnitOfWork(Protocol):
    cases: CaseDraftStore
    reviews: ReviewDraftAuthorizationStore
    deliveries: InboxDraftStore

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class InboxDraftUnitOfWorkFactory(Protocol):
    def __call__(self) -> InboxDraftUnitOfWork: ...
