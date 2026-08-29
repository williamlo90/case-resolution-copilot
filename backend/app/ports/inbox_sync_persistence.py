from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.domain.inbox import (
    InboxSyncJobRecord,
    InboxSyncWorkRecord,
    SyncRequest,
)

from .inbox_import_persistence import InboxCaseWriter, InboxMessageStore


class InboxSyncJobStore(Protocol):
    def enqueue(
        self,
        *,
        organization_public_id: str,
        request: SyncRequest,
    ) -> InboxSyncJobRecord: ...

    def claim(
        self,
        *,
        worker_id: str,
        limit: int,
        now: datetime,
        lease_seconds: int = 60,
        organization_public_id: str | None = None,
        connection_public_id: str | None = None,
    ) -> list[InboxSyncWorkRecord]: ...

    def get(self, *, job_id: UUID) -> InboxSyncJobRecord | None: ...

    def get_by_public_id(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> InboxSyncJobRecord | None: ...

    def reprocess(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> InboxSyncJobRecord: ...

    def complete(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        observed_history_id: str,
        next_page_token: str | None,
    ) -> None: ...

    def fail(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        error_code: str,
        reauthorize: bool,
    ) -> None: ...


class InboxSyncUnitOfWork(Protocol):
    jobs: InboxSyncJobStore
    cases: InboxCaseWriter
    messages: InboxMessageStore

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class InboxSyncUnitOfWorkFactory(Protocol):
    def __call__(self) -> InboxSyncUnitOfWork: ...
