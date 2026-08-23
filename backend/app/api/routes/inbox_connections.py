from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.dependencies.identity import current_actor
from app.api.errors import AppError
from app.api.inbox_support import INBOX_HANDLED_ERRORS, inbox_error, inbox_runtime
from app.api.schemas.inbox import (
    InboxAuthorizationCommand,
    InboxAuthorizationStartData,
    InboxAuthorizationStartEnvelope,
    InboxCallbackCommand,
    InboxCommandData,
    InboxCommandEnvelope,
    InboxConnectionData,
    InboxConnectionEnvelope,
    InboxConnectionStatusData,
    InboxConnectionStatusEnvelope,
    InboxImportCommand,
    InboxImportData,
    InboxImportEnvelope,
    InboxSyncJobData,
    InboxSyncJobEnvelope,
    InboxThreadData,
    InboxThreadListResponse,
)
from app.domain.identity import ActorContext
from app.domain.inbox import SelectedThreadImportCommand
from app.persistence.connection_persistence.status import InboxStatusRepository
from app.persistence.database import Database
from app.services.inbox.status import InboxStatusService

router = APIRouter(prefix="/api/connections", tags=["connected inbox"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="connected_inbox_not_configured",
            message="Connected inbox data is not available.",
            status_code=503,
        )
    return database


@router.get(
    "/{connection_id}/inbox/status",
    response_model=InboxConnectionStatusEnvelope,
)
def get_inbox_status(
    connection_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InboxConnectionStatusEnvelope:
    try:
        with _database(request).session() as session:
            result = InboxStatusService(InboxStatusRepository(session)).get(
                actor=actor,
                connection_id=connection_id,
            )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxConnectionStatusEnvelope(
        data=InboxConnectionStatusData.model_validate(result)
    )


@router.post("/inbox/authorize", response_model=InboxAuthorizationStartEnvelope)
def authorize_inbox(
    command: InboxAuthorizationCommand,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InboxAuthorizationStartEnvelope:
    try:
        result = inbox_runtime(request).authorization.start(
            actor=actor,
            include_drafts=command.include_drafts,
            return_path=command.return_path,
            login_hint=str(command.login_hint) if command.login_hint else None,
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxAuthorizationStartEnvelope(
        data=InboxAuthorizationStartData(
            authorization_url=result.authorization_url,
            expires_at=result.expires_at,
        )
    )


@router.post("/inbox/callback", response_model=InboxConnectionEnvelope)
def complete_inbox_authorization(
    command: InboxCallbackCommand,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InboxConnectionEnvelope:
    try:
        result = inbox_runtime(request).authorization.complete(
            actor=actor,
            state=command.state,
            code=command.code,
            correlation_id=str(request.state.correlation_id),
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxConnectionEnvelope(
        data=InboxConnectionData(
            connection_id=result.connection_public_id,
            account_address=result.account_address,
            return_path=result.return_path,
            capabilities=[item.value for item in result.granted_capabilities],
        )
    )


@router.get("/{connection_id}/inbox/threads", response_model=InboxThreadListResponse)
def list_inbox_threads(
    connection_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    cursor: str | None = Query(default=None, max_length=2000),
    limit: int = Query(default=5, ge=1, le=10),
) -> InboxThreadListResponse:
    try:
        result = inbox_runtime(request).browse.list_threads(
            actor=actor,
            connection_id=connection_id,
            page_token=cursor,
            limit=limit,
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxThreadListResponse(
        items=[InboxThreadData.model_validate(item) for item in result.items],
        next_cursor=result.next_page_token,
    )


@router.post(
    "/{connection_id}/imports",
    response_model=InboxImportEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def import_inbox_thread(
    connection_id: str,
    command: InboxImportCommand,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InboxImportEnvelope:
    try:
        result = inbox_runtime(request).imports.import_selected_thread(
            actor=actor,
            connection_id=connection_id,
            command=SelectedThreadImportCommand.model_validate(command.model_dump()),
            correlation_id=str(request.state.correlation_id),
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxImportEnvelope(
        data=InboxImportData(
            case_id=result.case_public_id,
            conversation_id=result.external_conversation_public_id,
            imported_messages=result.imported_messages,
            duplicate_messages=result.duplicate_messages,
            latest_message_at=result.latest_message_at,
        )
    )


@router.post("/{connection_id}/sync", response_model=InboxSyncJobEnvelope)
def request_inbox_sync(
    connection_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InboxSyncJobEnvelope:
    try:
        job = inbox_runtime(request).sync.request_manual(
            actor=actor,
            connection_id=connection_id,
            trigger_key=str(request.state.correlation_id),
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


@router.post("/{connection_id}/pause", response_model=InboxCommandEnvelope)
def pause_inbox(
    connection_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InboxCommandEnvelope:
    try:
        inbox_runtime(request).controls.pause(
            actor=actor,
            connection_id=connection_id,
            correlation_id=str(request.state.correlation_id),
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxCommandEnvelope(data=InboxCommandData(status="paused"))


@router.post("/{connection_id}/resume", response_model=InboxCommandEnvelope)
def resume_inbox(
    connection_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InboxCommandEnvelope:
    try:
        inbox_runtime(request).controls.resume(
            actor=actor,
            connection_id=connection_id,
            correlation_id=str(request.state.correlation_id),
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxCommandEnvelope(data=InboxCommandData(status="ready"))


@router.delete("/{connection_id}", response_model=InboxCommandEnvelope)
def disconnect_inbox(
    connection_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InboxCommandEnvelope:
    try:
        result = inbox_runtime(request).controls.disconnect(
            actor=actor,
            connection_id=connection_id,
            correlation_id=str(request.state.correlation_id),
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return InboxCommandEnvelope(
        data=InboxCommandData(
            status="disconnected",
            provider_revoked=result.provider_revoked,
        )
    )
