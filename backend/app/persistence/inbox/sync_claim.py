from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.domain.inbox import SyncJobStatus
from app.persistence.models import ConnectionModel, InboxSyncJobModel

MAX_SYNC_ATTEMPTS = 3


def claim_statement(
    *,
    now: datetime,
    limit: int,
    organization_id: UUID | None = None,
    connection_id: UUID | None = None,
) -> Select[tuple[InboxSyncJobModel]]:
    active_job = aliased(InboxSyncJobModel)
    active_lease_exists = (
        select(active_job.id)
        .where(
            active_job.organization_id == InboxSyncJobModel.organization_id,
            active_job.connection_id == InboxSyncJobModel.connection_id,
            active_job.status == SyncJobStatus.RUNNING.value,
            active_job.lease_expires_at.is_not(None),
            active_job.lease_expires_at > now,
        )
        .correlate(InboxSyncJobModel)
        .exists()
    )
    eligible = or_(
        InboxSyncJobModel.status.in_([SyncJobStatus.PENDING.value, SyncJobStatus.FAILED.value]),
        (
            (InboxSyncJobModel.status == SyncJobStatus.RUNNING.value)
            & (InboxSyncJobModel.lease_expires_at <= now)
        ),
    )
    filters = [
        eligible,
        InboxSyncJobModel.available_at <= now,
        InboxSyncJobModel.attempt_count < MAX_SYNC_ATTEMPTS,
        ~active_lease_exists,
    ]
    if organization_id is not None and connection_id is not None:
        filters.extend(
            [
                InboxSyncJobModel.organization_id == organization_id,
                InboxSyncJobModel.connection_id == connection_id,
            ]
        )
    ranked = (
        select(
            InboxSyncJobModel.id.label("job_id"),
            func.row_number()
            .over(
                partition_by=(
                    InboxSyncJobModel.organization_id,
                    InboxSyncJobModel.connection_id,
                ),
                order_by=(
                    InboxSyncJobModel.available_at,
                    InboxSyncJobModel.created_at,
                ),
            )
            .label("connection_rank"),
        )
        .where(*filters)
        .subquery("ranked_inbox_sync_jobs")
    )
    return (
        select(InboxSyncJobModel)
        .join(ranked, ranked.c.job_id == InboxSyncJobModel.id)
        .join(
            ConnectionModel,
            (ConnectionModel.organization_id == InboxSyncJobModel.organization_id)
            & (ConnectionModel.id == InboxSyncJobModel.connection_id),
        )
        .where(ranked.c.connection_rank == 1)
        .order_by(InboxSyncJobModel.available_at, InboxSyncJobModel.created_at)
        .with_for_update(
            of=(InboxSyncJobModel, ConnectionModel),
            skip_locked=True,
        )
        .limit(limit)
    )


def exhausted_lease_statement(
    *,
    now: datetime,
    limit: int,
    organization_id: UUID | None = None,
    connection_id: UUID | None = None,
) -> Select[tuple[InboxSyncJobModel]]:
    filters = [
        InboxSyncJobModel.status == SyncJobStatus.RUNNING.value,
        InboxSyncJobModel.lease_expires_at <= now,
        InboxSyncJobModel.attempt_count >= MAX_SYNC_ATTEMPTS,
    ]
    if organization_id is not None and connection_id is not None:
        filters.extend(
            [
                InboxSyncJobModel.organization_id == organization_id,
                InboxSyncJobModel.connection_id == connection_id,
            ]
        )
    return (
        select(InboxSyncJobModel)
        .where(*filters)
        .order_by(InboxSyncJobModel.lease_expires_at)
        .with_for_update(skip_locked=True)
        .limit(limit)
    )
