from collections.abc import Callable, Iterator
from dataclasses import dataclass
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.identity import (
    authenticate_actor,
    authorize_actor,
    current_actor,
)
from app.api.errors import AppError
from app.api.middleware import add_server_timing
from app.api.presenters.cases import (
    present_case_activity,
    present_case_queue_summary,
    present_case_summary,
    present_case_workspace,
    present_conversation,
    present_conversation_message,
)
from app.api.schemas.cases import (
    AddCaseEvidenceRequest,
    AssignCaseRequest,
    CaseActivityPageResponse,
    CaseDetailResponse,
    CaseListResponse,
    ChangeCaseStatusRequest,
)
from app.api.schemas.conversations import (
    AddConversationMessageRequest,
    AddInternalNoteRequest,
    ConversationDetailResponse,
    ConversationMessagePageResponse,
    SaveDraftRequest,
)
from app.domain.cases import (
    BusinessEvidenceConflict,
    BusinessEvidenceCreate,
    BusinessEvidenceNotAllowed,
    CaseActorNotAssignable,
    CaseCategory,
    CaseConcurrencyConflict,
    CaseNotFound,
    CaseQueueSort,
    CaseQueueView,
    CaseStatus,
    CaseWorkspaceRecord,
    DraftConcurrencyConflict,
    InvalidCaseTransition,
    MessageChannel,
)
from app.domain.identity import ActorContext, Permission
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.policy_repository import PolicyRepository
from app.persistence.review_repository import ReviewRepository
from app.services.case_history_service import (
    CaseHistoryService,
    InvalidCaseHistoryCursor,
)
from app.services.case_service import CaseService, InvalidCaseCursor, encode_cursor
from app.services.case_workspace_query import CaseWorkspaceQueryService

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Case data is not available.",
            status_code=503,
        )
    return database


@dataclass(frozen=True, slots=True)
class _CaseRequestContext:
    actor: ActorContext
    session: Session


def _case_request_context(
    request: Request,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-ID")] = None,
) -> Iterator[_CaseRequestContext]:
    database: Database | None = request.app.state.database
    if database is None:
        authenticate_actor(request, x_actor_id)
        database = _database(request)

    with database.session() as session:
        actor = authenticate_actor(
            request,
            x_actor_id,
            session=session,
        )
        yield _CaseRequestContext(actor=actor, session=session)


def _translate(error: Exception) -> AppError:
    if isinstance(error, CaseNotFound):
        return AppError(code="case_not_found", message=str(error), status_code=404)
    if isinstance(error, CaseActorNotAssignable):
        return AppError(code="case_assignment_forbidden", message=str(error), status_code=403)
    if isinstance(error, InvalidCaseCursor):
        return AppError(code="invalid_case_cursor", message=str(error), status_code=400)
    if isinstance(error, InvalidCaseHistoryCursor):
        return AppError(code="invalid_case_history_cursor", message=str(error), status_code=400)
    if isinstance(error, InvalidCaseTransition):
        return AppError(code="invalid_case_transition", message=str(error), status_code=409)
    if isinstance(error, BusinessEvidenceConflict):
        return AppError(code="case_evidence_conflict", message=str(error), status_code=409)
    if isinstance(error, BusinessEvidenceNotAllowed):
        return AppError(code="case_evidence_not_allowed", message=str(error), status_code=409)
    if isinstance(error, (CaseConcurrencyConflict, DraftConcurrencyConflict)):
        return AppError(
            code="version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    return AppError(code="case_operation_failed", message=str(error), status_code=409)


def _workspace_query(session: Session) -> CaseWorkspaceQueryService:
    return CaseWorkspaceQueryService(
        cases=CaseRepository(session),
        decisions=DecisionBriefRepository(session),
        policies=PolicyRepository(session),
        reviews=ReviewRepository(session),
    )


def _execute_case_command(
    actor: ActorContext,
    operation: Callable[[], CaseWorkspaceRecord],
    session: Session,
) -> CaseDetailResponse:
    try:
        workspace = operation()
    except (
        CaseActorNotAssignable,
        BusinessEvidenceConflict,
        BusinessEvidenceNotAllowed,
        CaseConcurrencyConflict,
        CaseNotFound,
        DraftConcurrencyConflict,
        InvalidCaseTransition,
    ) as exc:
        raise _translate(exc) from exc
    projection = _workspace_query(session).project(actor=actor, workspace=workspace)
    return CaseDetailResponse(
        data=present_case_workspace(
            projection,
            organization_id=actor.organization_id,
        )
    )


@router.get("", response_model=CaseListResponse)
def list_cases(
    request: Request,
    context: Annotated[_CaseRequestContext, Depends(_case_request_context)],
    status: Annotated[CaseStatus | None, Query()] = None,
    category: Annotated[CaseCategory | None, Query()] = None,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    view: Annotated[CaseQueueView, Query()] = CaseQueueView.ALL,
    sort: Annotated[CaseQueueSort, Query()] = CaseQueueSort.PRIORITY,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CaseListResponse:
    del request
    actor = context.actor
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    try:
        page = CaseService(CaseRepository(context.session)).list_cases(
            actor=actor,
            status=status,
            category=category,
            query=query,
            cursor=cursor,
            limit=limit,
            view=view,
            sort=sort,
        )
    except (CaseNotFound, InvalidCaseCursor) as exc:
        raise _translate(exc) from exc
    return CaseListResponse(
        items=[
            present_case_summary(item, organization_id=actor.organization_id)
            for item in page.items
        ],
        next_cursor=encode_cursor(
            page.next_cursor,
            status=status,
            category=category,
            query=query,
            view=view,
            sort=sort,
        ),
        previous_cursor=encode_cursor(
            page.previous_cursor,
            status=status,
            category=category,
            query=query,
            view=view,
            sort=sort,
        ),
        total=page.total,
        offset=page.offset,
        limit=page.limit,
        summary_scope=page.summary_scope,
        summary=present_case_queue_summary(page.summary),
    )


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: str,
    request: Request,
    context: Annotated[_CaseRequestContext, Depends(_case_request_context)],
) -> CaseDetailResponse:
    actor = context.actor
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    try:
        store_started_at = perf_counter()
        projection = _workspace_query(context.session).get(
            actor=actor,
            case_id=case_id,
        )
        add_server_timing(
            request,
            "case_store",
            (perf_counter() - store_started_at) * 1000,
        )
        presentation_started_at = perf_counter()
        response = CaseDetailResponse(
            data=present_case_workspace(
                projection,
                organization_id=actor.organization_id,
            )
        )
        add_server_timing(
            request,
            "case_present",
            (perf_counter() - presentation_started_at) * 1000,
        )
        return response
    except CaseNotFound as exc:
        raise _translate(exc) from exc


@router.get("/{case_id}/conversation", response_model=ConversationDetailResponse)
def get_conversation(
    case_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ConversationDetailResponse:
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    try:
        with _database(request).session() as session:
            workspace = CaseService(CaseRepository(session)).get_case(
                actor=actor,
                case_id=case_id,
            )
    except CaseNotFound as exc:
        raise _translate(exc) from exc
    return ConversationDetailResponse(
        data=present_conversation(workspace, organization_id=actor.organization_id)
    )


@router.get(
    "/{case_id}/conversation/history",
    response_model=ConversationMessagePageResponse,
)
def get_conversation_history(
    case_id: str,
    context: Annotated[_CaseRequestContext, Depends(_case_request_context)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ConversationMessagePageResponse:
    actor = context.actor
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    try:
        page = CaseHistoryService(CaseRepository(context.session)).conversation(
            actor=actor,
            case_id=case_id,
            cursor=cursor,
            limit=limit,
        )
    except (CaseNotFound, InvalidCaseHistoryCursor) as exc:
        raise _translate(exc) from exc
    return ConversationMessagePageResponse(
        items=[
            present_conversation_message(
                message,
                organization_id=actor.organization_id,
                case_id=case_id,
            )
            for message in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@router.get(
    "/{case_id}/activity/history",
    response_model=CaseActivityPageResponse,
)
def get_case_activity_history(
    case_id: str,
    context: Annotated[_CaseRequestContext, Depends(_case_request_context)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> CaseActivityPageResponse:
    actor = context.actor
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    try:
        page = CaseHistoryService(CaseRepository(context.session)).activity(
            actor=actor,
            case_id=case_id,
            cursor=cursor,
            limit=limit,
        )
    except (CaseNotFound, InvalidCaseHistoryCursor) as exc:
        raise _translate(exc) from exc
    return CaseActivityPageResponse(
        items=[present_case_activity(activity) for activity in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@router.post("/{case_id}/assign", response_model=CaseDetailResponse)
def assign_case(
    case_id: str,
    command: AssignCaseRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> CaseDetailResponse:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    with _database(request).session() as session:
        service = CaseService(CaseRepository(session))
        return _execute_case_command(
            actor,
            lambda: service.assign_to_me(
                actor=actor,
                case_id=case_id,
                expected_version=command.expected_version,
                correlation_id=str(request.state.correlation_id),
            ),
            session,
        )


@router.post("/{case_id}/status", response_model=CaseDetailResponse)
def change_case_status(
    case_id: str,
    command: ChangeCaseStatusRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> CaseDetailResponse:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    with _database(request).session() as session:
        service = CaseService(CaseRepository(session))
        return _execute_case_command(
            actor,
            lambda: service.change_status(
                actor=actor,
                case_id=case_id,
                expected_version=command.expected_version,
                target=command.status,
                correlation_id=str(request.state.correlation_id),
            ),
            session,
        )


@router.post("/{case_id}/messages", response_model=CaseDetailResponse)
def add_case_message(
    case_id: str,
    command: AddConversationMessageRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> CaseDetailResponse:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    with _database(request).session() as session:
        service = CaseService(CaseRepository(session))
        return _execute_case_command(
            actor,
            lambda: service.add_message(
                actor=actor,
                case_id=case_id,
                expected_case_version=command.expected_case_version,
                channel=MessageChannel(command.channel),
                body=command.body,
                correlation_id=str(request.state.correlation_id),
            ),
            session,
        )


@router.post("/{case_id}/notes", response_model=CaseDetailResponse)
def add_internal_note(
    case_id: str,
    command: AddInternalNoteRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> CaseDetailResponse:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    with _database(request).session() as session:
        service = CaseService(CaseRepository(session))
        return _execute_case_command(
            actor,
            lambda: service.add_message(
                actor=actor,
                case_id=case_id,
                expected_case_version=command.expected_case_version,
                channel=MessageChannel.INTERNAL_NOTE,
                body=command.body,
                correlation_id=str(request.state.correlation_id),
            ),
            session,
        )


@router.post("/{case_id}/evidence-records", response_model=CaseDetailResponse)
def add_case_evidence(
    case_id: str,
    command: AddCaseEvidenceRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> CaseDetailResponse:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    with _database(request).session() as session:
        service = CaseService(CaseRepository(session))
        return _execute_case_command(
            actor,
            lambda: service.add_business_evidence(
                actor=actor,
                case_id=case_id,
                expected_case_version=command.expected_case_version,
                evidence=BusinessEvidenceCreate(
                    type=command.type,
                    label=command.label,
                    source=command.source,
                    source_reference=command.source_reference,
                    status=command.status,
                    fields=command.fields,
                ),
                correlation_id=str(request.state.correlation_id),
            ),
            session,
        )


@router.post("/{case_id}/draft", response_model=CaseDetailResponse)
def save_response_draft(
    case_id: str,
    command: SaveDraftRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> CaseDetailResponse:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    with _database(request).session() as session:
        service = CaseService(CaseRepository(session))
        return _execute_case_command(
            actor,
            lambda: service.save_draft(
                actor=actor,
                case_id=case_id,
                expected_version=command.expected_version,
                subject=command.subject,
                body=command.body,
                correlation_id=str(request.state.correlation_id),
            ),
            session,
        )
