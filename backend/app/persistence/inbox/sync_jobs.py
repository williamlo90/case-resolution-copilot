from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.inbox import (
    InboxSyncJobRecord,
    InboxSyncWorkRecord,
    SyncJobStatus,
    SyncRequest,
)
from app.persistence.models import (
    ConnectionModel,
    InboxConnectionProfileModel,
    InboxSyncCheckpointModel,
    InboxSyncJobModel,
    OrganizationModel,
    utc_now,
)

from ._base import InboxRepositoryBase
from .sync_claim import MAX_SYNC_ATTEMPTS, exhausted_lease_statement
from .sync_claim import claim_statement as _claim_statement


class InboxSyncJobRepository(InboxRepositoryBase):
    def enqueue(
        self,
        *,
        organization_public_id: str,
        request: SyncRequest,
    ) -> InboxSyncJobRecord:
        connection = self._connection(
            organization_public_id,
            request.connection_public_id,
            for_update=True,
        )
        existing = self._session.scalar(
            select(InboxSyncJobModel).where(
                InboxSyncJobModel.organization_id == connection.organization_id,
                InboxSyncJobModel.connection_id == connection.id,
                InboxSyncJobModel.trigger_key == request.trigger_key,
            )
        )
        if existing is not None:
            return InboxSyncJobRecord.model_validate(existing)
        active = self._session.scalar(
            select(InboxSyncJobModel)
            .where(
                InboxSyncJobModel.organization_id == connection.organization_id,
                InboxSyncJobModel.connection_id == connection.id,
                InboxSyncJobModel.status.in_(
                    [
                        SyncJobStatus.PENDING.value,
                        SyncJobStatus.RUNNING.value,
                        SyncJobStatus.FAILED.value,
                    ]
                ),
                InboxSyncJobModel.attempt_count < MAX_SYNC_ATTEMPTS,
            )
            .order_by(
                InboxSyncJobModel.available_at,
                InboxSyncJobModel.created_at,
            )
        )
        if active is not None:
            return InboxSyncJobRecord.model_validate(active)
        now = utc_now()
        model = InboxSyncJobModel(
            public_id=f"ISJ-{uuid4().hex[:12].upper()}",
            organization_id=connection.organization_id,
            connection_id=connection.id,
            trigger=request.trigger.value,
            trigger_key=request.trigger_key,
            requested_history_id=request.requested_history_id,
            page_token=request.page_token,
            status=SyncJobStatus.PENDING.value,
            page_budget=request.page_budget,
            item_budget=request.item_budget,
            attempt_count=0,
            available_at=now,
            lease_owner=None,
            lease_expires_at=None,
            last_error_code=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        self._session.flush()
        return InboxSyncJobRecord.model_validate(model)

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
        if (organization_public_id is None) != (connection_public_id is None):
            raise ValueError("Organization and connection filters must be supplied together.")
        organization_id: UUID | None = None
        connection_id: UUID | None = None
        if organization_public_id is not None and connection_public_id is not None:
            connection = self._connection(
                organization_public_id,
                connection_public_id,
            )
            organization_id = connection.organization_id
            connection_id = connection.id
        exhausted = self._session.scalars(
            exhausted_lease_statement(
                now=now,
                limit=limit,
                organization_id=organization_id,
                connection_id=connection_id,
            )
        )
        for job in exhausted:
            job.status = SyncJobStatus.DEAD.value
            job.last_error_code = "worker_lost"
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = now
            checkpoint = self._checkpoint(job.organization_id, job.connection_id)
            checkpoint.status = "failed"
            checkpoint.consecutive_failures += 1
            checkpoint.last_attempt_at = now
            checkpoint.last_error_code = "worker_lost"
            checkpoint.version += 1
            checkpoint.updated_at = now
        jobs = list(
            self._session.scalars(
                _claim_statement(
                    now=now,
                    limit=limit,
                    organization_id=organization_id,
                    connection_id=connection_id,
                )
            )
        )
        result: list[InboxSyncWorkRecord] = []
        for job in jobs:
            job.status = SyncJobStatus.RUNNING.value
            job.attempt_count += 1
            job.lease_owner = worker_id
            job.lease_expires_at = now + timedelta(seconds=lease_seconds)
            job.updated_at = now
            checkpoint = self._checkpoint(job.organization_id, job.connection_id)
            organization_public_id = self._session.scalar(
                select(OrganizationModel.public_id).where(
                    OrganizationModel.id == job.organization_id
                )
            )
            connection_public_id = self._session.scalar(
                select(ConnectionModel.public_id).where(ConnectionModel.id == job.connection_id)
            )
            if organization_public_id is None or connection_public_id is None:
                continue
            result.append(
                InboxSyncWorkRecord(
                    job=InboxSyncJobRecord.model_validate(job),
                    organization_public_id=organization_public_id,
                    connection_public_id=connection_public_id,
                    committed_history_id=checkpoint.provider_history_id,
                )
            )
        self._session.flush()
        return result

    def get(self, *, job_id: UUID) -> InboxSyncJobRecord | None:
        job = self._session.get(InboxSyncJobModel, job_id)
        return InboxSyncJobRecord.model_validate(job) if job is not None else None

    def get_by_public_id(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> InboxSyncJobRecord | None:
        job = self._session.scalar(
            select(InboxSyncJobModel)
            .join(OrganizationModel, OrganizationModel.id == InboxSyncJobModel.organization_id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                InboxSyncJobModel.public_id == job_public_id,
            )
        )
        return InboxSyncJobRecord.model_validate(job) if job is not None else None

    def reprocess(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> InboxSyncJobRecord:
        job = self._session.scalar(
            select(InboxSyncJobModel)
            .join(OrganizationModel, OrganizationModel.id == InboxSyncJobModel.organization_id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                InboxSyncJobModel.public_id == job_public_id,
            )
            .with_for_update()
        )
        if job is None:
            raise LookupError("The inbox sync job was not found.")
        if job.status != SyncJobStatus.DEAD.value:
            return InboxSyncJobRecord.model_validate(job)
        now = utc_now()
        job.status = SyncJobStatus.PENDING.value
        job.attempt_count = 0
        job.available_at = now
        job.lease_owner = None
        job.lease_expires_at = None
        job.completed_at = None
        job.updated_at = now
        checkpoint = self._checkpoint(job.organization_id, job.connection_id)
        checkpoint.status = "delayed"
        checkpoint.version += 1
        checkpoint.updated_at = now
        self._session.flush()
        return InboxSyncJobRecord.model_validate(job)

    def complete(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        observed_history_id: str,
        next_page_token: str | None,
    ) -> None:
        job = self._running_job(job_id, worker_id=worker_id)
        now = utc_now()
        checkpoint = self._checkpoint(job.organization_id, job.connection_id)
        checkpoint.last_observed_history_id = observed_history_id
        checkpoint.last_attempt_at = now
        checkpoint.consecutive_failures = 0
        checkpoint.last_error_code = None
        checkpoint.status = "current" if next_page_token is None else "syncing"
        checkpoint.version += 1
        checkpoint.updated_at = now
        if next_page_token is None:
            checkpoint.provider_history_id = observed_history_id
            checkpoint.last_successful_sync_at = now
            profile = self._session.scalar(
                select(InboxConnectionProfileModel).where(
                    InboxConnectionProfileModel.organization_id == job.organization_id,
                    InboxConnectionProfileModel.connection_id == job.connection_id,
                )
            )
            if profile is not None:
                profile.last_successful_sync_at = now
                profile.updated_at = now
        else:
            continuation_key = (
                f"{job.trigger_key}:page:{sha256(next_page_token.encode()).hexdigest()[:12]}"
            )
            self._session.add(
                InboxSyncJobModel(
                    public_id=f"ISJ-{uuid4().hex[:12].upper()}",
                    organization_id=job.organization_id,
                    connection_id=job.connection_id,
                    trigger=job.trigger,
                    trigger_key=continuation_key,
                    requested_history_id=(
                        job.requested_history_id or checkpoint.provider_history_id
                    ),
                    page_token=next_page_token,
                    status="pending",
                    page_budget=job.page_budget,
                    item_budget=job.item_budget,
                    attempt_count=0,
                    available_at=now,
                    lease_owner=None,
                    lease_expires_at=None,
                    last_error_code=None,
                    completed_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        job.status = SyncJobStatus.COMPLETED.value
        job.completed_at = now
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = now

    def fail(
        self,
        *,
        job_id: UUID,
        worker_id: str,
        error_code: str,
        reauthorize: bool,
    ) -> None:
        job = self._running_job(job_id, worker_id=worker_id)
        now = utc_now()
        dead = job.attempt_count >= MAX_SYNC_ATTEMPTS or reauthorize
        job.status = "dead" if dead else "failed"
        job.available_at = now + timedelta(seconds=2**job.attempt_count)
        job.last_error_code = error_code[:100]
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = now
        checkpoint = self._checkpoint(job.organization_id, job.connection_id)
        checkpoint.status = "reauthorize" if reauthorize else ("failed" if dead else "delayed")
        checkpoint.consecutive_failures += 1
        checkpoint.last_attempt_at = now
        checkpoint.last_error_code = error_code[:100]
        checkpoint.version += 1
        checkpoint.updated_at = now

    def _running_job(self, job_id: UUID, *, worker_id: str) -> InboxSyncJobModel:
        job = self._session.scalar(
            select(InboxSyncJobModel)
            .where(
                InboxSyncJobModel.id == job_id,
                InboxSyncJobModel.status == "running",
                InboxSyncJobModel.lease_owner == worker_id,
                InboxSyncJobModel.lease_expires_at > datetime.now(UTC),
            )
            .with_for_update()
        )
        if job is None:
            raise LookupError("The inbox sync lease is no longer active.")
        return job

    def _checkpoint(
        self,
        organization_id: UUID,
        connection_id: UUID,
    ) -> InboxSyncCheckpointModel:
        checkpoint = self._session.scalar(
            select(InboxSyncCheckpointModel)
            .where(
                InboxSyncCheckpointModel.organization_id == organization_id,
                InboxSyncCheckpointModel.connection_id == connection_id,
            )
            .with_for_update()
        )
        if checkpoint is None:
            raise LookupError("The inbox sync checkpoint was not found.")
        return checkpoint
