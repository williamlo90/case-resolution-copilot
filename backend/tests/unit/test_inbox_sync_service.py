from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

from app.domain.inbox import (
    InboxCredentialUnavailable,
    InboxSyncJobRecord,
    InboxSyncWorkRecord,
    SyncJobStatus,
    SyncRequest,
    SyncTrigger,
)
from app.ports.inbox import InboxReadGateway, InboxReadGatewayResolver
from app.ports.inbox_access import InboxAccessProvider
from app.ports.inbox_import_persistence import InboxCaseWriter, InboxMessageStore
from app.ports.inbox_sync_persistence import InboxSyncJobStore, InboxSyncUnitOfWork
from app.security.authentication import DeterministicAuthProvider
from app.services.inbox.sync import InboxSyncService

NOW = datetime(2026, 8, 23, 8, 0, tzinfo=UTC)


def _job() -> InboxSyncJobRecord:
    return InboxSyncJobRecord(
        id=uuid4(),
        public_id="ISJ-UNIT-0001",
        organization_id=uuid4(),
        connection_id=uuid4(),
        trigger=SyncTrigger.MANUAL,
        trigger_key="manual-unit",
        requested_history_id=None,
        page_token=None,
        status=SyncJobStatus.RUNNING,
        page_budget=1,
        item_budget=5,
        attempt_count=1,
        available_at=NOW,
        lease_owner="worker-unit",
        lease_expires_at=NOW + timedelta(seconds=60),
        last_error_code=None,
        completed_at=None,
        created_at=NOW,
    )


class _JobStore:
    def __init__(self, work: InboxSyncWorkRecord) -> None:
        self.work = work
        self.claimed = False
        self.claim_scope: tuple[str | None, str | None] | None = None
        self.lease_seconds: int | None = None
        self.failure: tuple[UUID, str, str, bool] | None = None

    def enqueue(
        self,
        *,
        organization_public_id: str,
        request: SyncRequest,
    ) -> InboxSyncJobRecord:
        del organization_public_id, request
        raise AssertionError("This test does not enqueue jobs.")

    def claim(
        self,
        *,
        worker_id: str,
        limit: int,
        now: datetime,
        lease_seconds: int = 60,
        organization_public_id: str | None = None,
        connection_public_id: str | None = None,
    ) -> list[InboxSyncWorkRecord]:
        del worker_id, limit, now
        self.lease_seconds = lease_seconds
        self.claim_scope = (organization_public_id, connection_public_id)
        if self.claimed:
            return []
        self.claimed = True
        return [self.work]

    def get(self, *, job_id: UUID) -> InboxSyncJobRecord | None:
        return self.work.job if job_id == self.work.job.id else None

    def get_by_public_id(
        self, *, organization_public_id: str, job_public_id: str
    ) -> InboxSyncJobRecord | None:
        return (
            self.work.job
            if organization_public_id == self.work.organization_public_id
            and job_public_id == self.work.job.public_id
            else None
        )

    def reprocess(self, *, organization_public_id: str, job_public_id: str) -> InboxSyncJobRecord:
        if (
            organization_public_id != self.work.organization_public_id
            or job_public_id != self.work.job.public_id
        ):
            raise LookupError("The inbox sync job was not found.")
        if self.work.job.status == SyncJobStatus.DEAD:
            self.work = self.work.model_copy(
                update={
                    "job": self.work.job.model_copy(
                        update={"status": SyncJobStatus.PENDING, "attempt_count": 0}
                    )
                }
            )
        return self.work.job

    def complete(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        observed_history_id: str,
        next_page_token: str | None,
    ) -> None:
        del job_id, worker_id, observed_history_id, next_page_token
        raise AssertionError("A failed fetch cannot complete its job.")

    def fail(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        error_code: str,
        reauthorize: bool,
    ) -> None:
        self.failure = (job_id, worker_id, error_code, reauthorize)


class _UnitOfWork:
    def __init__(self, jobs: _JobStore) -> None:
        self.jobs: InboxSyncJobStore = jobs
        self.cases = cast(InboxCaseWriter, object())
        self.messages = cast(InboxMessageStore, object())

    def __enter__(self) -> "_UnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


class _Factory:
    def __init__(self, jobs: _JobStore) -> None:
        self.jobs = jobs

    def __call__(self) -> InboxSyncUnitOfWork:
        return _UnitOfWork(self.jobs)


class _UnavailableAccess:
    def access(self, *, organization_id: str, connection_id: str) -> None:
        del organization_id, connection_id
        raise InboxCredentialUnavailable("Credential key is unavailable.")


class _UnusedGateways:
    def reader(self, adapter_key: str) -> InboxReadGateway:
        del adapter_key
        raise AssertionError("Credential lookup must fail before provider access.")


def test_credential_failure_releases_the_job_for_reauthorization() -> None:
    actor = DeterministicAuthProvider().authenticate("USR-0003")
    work = InboxSyncWorkRecord(
        job=_job(),
        organization_public_id=actor.organization_id,
        connection_public_id="CON-INBOX-UNIT",
        committed_history_id="history-1",
    )
    jobs = _JobStore(work)
    service = InboxSyncService(
        unit_of_work=_Factory(jobs),
        gateways=cast(InboxReadGatewayResolver, _UnusedGateways()),
        access=cast(InboxAccessProvider, _UnavailableAccess()),
        lease_seconds=150,
    )

    result = service.drain(
        worker_id="worker-unit",
        limit=1,
        organization_id=actor.organization_id,
        connection_id="CON-INBOX-UNIT",
    )

    assert result.claimed_jobs == 1
    assert result.completed_jobs == 0
    assert result.failed_jobs == 1
    assert jobs.claim_scope == (actor.organization_id, "CON-INBOX-UNIT")
    assert jobs.lease_seconds == 150
    assert jobs.failure == (
        work.job.id,
        "worker-unit",
        "credential_unavailable",
        True,
    )


def test_dead_job_reprocessing_is_idempotent() -> None:
    actor = DeterministicAuthProvider().authenticate("USR-0003")
    work = InboxSyncWorkRecord(
        job=_job().model_copy(update={"status": SyncJobStatus.DEAD, "attempt_count": 3}),
        organization_public_id=actor.organization_id,
        connection_public_id="CON-INBOX-UNIT",
        committed_history_id="history-1",
    )
    jobs = _JobStore(work)
    service = InboxSyncService(
        unit_of_work=_Factory(jobs),
        gateways=cast(InboxReadGatewayResolver, _UnusedGateways()),
        access=cast(InboxAccessProvider, _UnavailableAccess()),
    )

    first = service.reprocess(
        organization_public_id=work.organization_public_id,
        job_public_id=work.job.public_id,
    )
    duplicate = service.reprocess(
        organization_public_id=work.organization_public_id,
        job_public_id=work.job.public_id,
    )

    assert first.status == SyncJobStatus.PENDING
    assert first.attempt_count == 0
    assert duplicate == first
