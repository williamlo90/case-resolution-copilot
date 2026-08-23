from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.api.errors import AppError
from app.api.inbox_support import INBOX_HANDLED_ERRORS, inbox_error, inbox_runtime
from app.api.schemas.inbox import (
    InboxSyncJobData,
    InboxSyncJobEnvelope,
    ScheduledSyncCommand,
    SyncDrainData,
    SyncDrainEnvelope,
)

router = APIRouter(prefix="/api/internal/inbox-sync", tags=["internal inbox sync"])
SCHEDULER_HEADER = "X-Inbox-Scheduler-Secret"


def _authenticate_scheduler(request: Request, provided: str | None) -> None:
    settings = request.app.state.settings
    expected = settings.inbox_scheduler_secret_value()
    if not settings.inbox_scheduled_sync_enabled or expected is None:
        raise AppError(
            code="inbox_scheduler_disabled",
            message="Scheduled inbox synchronization is not enabled.",
            status_code=503,
        )
    if provided is None or not compare_digest(provided, expected):
        raise AppError(
            code="inbox_scheduler_unauthorized",
            message="The scheduler request could not be verified.",
            status_code=401,
        )


@router.post("/schedule", response_model=InboxSyncJobEnvelope)
def schedule_sync(
    command: ScheduledSyncCommand,
    request: Request,
    scheduler_secret: Annotated[str | None, Header(alias=SCHEDULER_HEADER)] = None,
) -> InboxSyncJobEnvelope:
    _authenticate_scheduler(request, scheduler_secret)
    try:
        job = inbox_runtime(request).sync.request_scheduled(
            organization_id=command.organization_id,
            connection_id=command.connection_id,
            trigger_key=command.trigger_key,
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxSyncJobEnvelope(
        data=InboxSyncJobData(
            id=job.public_id,
            status=job.status,
            attempt_count=job.attempt_count,
        )
    )


@router.post("/drain", response_model=SyncDrainEnvelope)
def drain_sync_jobs(
    request: Request,
    scheduler_secret: Annotated[str | None, Header(alias=SCHEDULER_HEADER)] = None,
) -> SyncDrainEnvelope:
    _authenticate_scheduler(request, scheduler_secret)
    settings = request.app.state.settings
    try:
        result = inbox_runtime(request).sync.drain(
            worker_id=str(request.state.correlation_id),
            limit=settings.inbox_sync_job_limit,
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return SyncDrainEnvelope(data=SyncDrainData.model_validate(result))
