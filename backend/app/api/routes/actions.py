from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.errors import AppError
from app.api.presenters.actions import (
    present_action_detail,
    present_action_summary,
)
from app.api.schemas.actions import (
    ActionDetailEnvelope,
    ActionListResponse,
    EscalateActionRequest,
    ExecuteActionRequest,
    ReconcileActionRequest,
    RecordManualOutcomeRequest,
)
from app.domain.actions import (
    ActionConflict,
    ActionExecutionBlocked,
    ActionExecutionBlocker,
    ActionNotFound,
    ActionStatus,
    ActionVersionConflict,
    InvalidActionCursor,
)
from app.domain.identity import (
    ActorContext,
    ActorMembershipNotFound,
    Permission,
)
from app.integrations.action_gateway import ActionGateway
from app.persistence.action_repository import ActionRepository
from app.persistence.database import Database
from app.services.action_service import ActionCommandService, ActionQueryService

router = APIRouter(prefix="/api/actions", tags=["actions"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Action data is not available.",
            status_code=503,
        )
    return database


def _gateway(request: Request) -> ActionGateway:
    gateway: ActionGateway | None = request.app.state.action_gateway
    if gateway is None:
        raise AppError(
            code="action_gateway_not_configured",
            message="Controlled actions are not available.",
            status_code=503,
        )
    return gateway


def _query_service(session: Session) -> ActionQueryService:
    return ActionQueryService(ActionRepository(session))


def _command_service(request: Request) -> ActionCommandService:
    return ActionCommandService(_database(request), _gateway(request))


def _translate(error: Exception) -> AppError:
    if isinstance(error, ActionNotFound):
        return AppError(
            code="action_not_found",
            message=str(error),
            status_code=404,
        )
    if isinstance(error, ActorMembershipNotFound):
        return AppError(
            code="active_membership_required",
            message=str(error),
            status_code=403,
        )
    if isinstance(error, InvalidActionCursor):
        return AppError(
            code="invalid_action_cursor",
            message=str(error),
            status_code=400,
        )
    if isinstance(error, ActionVersionConflict):
        return AppError(
            code="version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    if isinstance(error, ActionExecutionBlocked):
        return AppError(
            code="action_execution_blocked",
            message=str(error),
            status_code=(
                424 if error.blocker is ActionExecutionBlocker.CONNECTION_UNAVAILABLE else 409
            ),
            details={"blocker": error.blocker.value},
        )
    if isinstance(error, ActionConflict):
        return AppError(
            code="action_conflict",
            message=str(error),
            status_code=409,
        )
    return AppError(
        code="action_failed",
        message="The action command could not be completed.",
        status_code=409,
    )


@router.get("", response_model=ActionListResponse)
def list_actions(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    status: ActionStatus | None = None,
    recovery_required: bool | None = None,
    query: str | None = Query(default=None, max_length=200),
    cursor: str | None = Query(default=None, max_length=2000),
    limit: int = Query(default=50, ge=1, le=100),
) -> ActionListResponse:
    authorize_actor(actor, Permission.ACTION_READ, error_code="action_read_forbidden")
    try:
        with _database(request).session() as session:
            page = _query_service(session).list(
                actor=actor,
                status=status.value if status is not None else None,
                recovery_required=recovery_required,
                query=query,
                cursor=cursor,
                limit=limit,
            )
    except (ActionConflict, InvalidActionCursor) as exc:
        raise _translate(exc) from exc
    return ActionListResponse(
        items=[
            present_action_summary(
                item,
                organization_id=actor.organization_id,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@router.get("/{action_id}", response_model=ActionDetailEnvelope)
def get_action(
    action_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ActionDetailEnvelope:
    authorize_actor(actor, Permission.ACTION_READ, error_code="action_read_forbidden")
    try:
        with _database(request).session() as session:
            item = _query_service(session).get(
                actor=actor,
                action_id=action_id,
            )
    except (ActionConflict, ActionNotFound) as exc:
        raise _translate(exc) from exc
    return ActionDetailEnvelope(data=present_action_detail(item, actor=actor))


@router.post("/{action_id}/execute", response_model=ActionDetailEnvelope)
def execute_action(
    action_id: str,
    command: ExecuteActionRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ActionDetailEnvelope:
    authorize_actor(
        actor,
        Permission.ACTION_EXECUTE,
        error_code="action_execute_forbidden",
    )
    try:
        item = _command_service(request).execute(
            actor=actor,
            action_id=action_id,
            expected_version=command.expected_version,
            correlation_id=str(request.state.correlation_id),
        )
    except (
        ActionConflict,
        ActionExecutionBlocked,
        ActionNotFound,
        ActionVersionConflict,
        ActorMembershipNotFound,
    ) as exc:
        raise _translate(exc) from exc
    return ActionDetailEnvelope(data=present_action_detail(item, actor=actor))


@router.post("/{action_id}/retry", response_model=ActionDetailEnvelope)
def retry_action(
    action_id: str,
    command: ExecuteActionRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ActionDetailEnvelope:
    authorize_actor(
        actor,
        Permission.ACTION_EXECUTE,
        error_code="action_execute_forbidden",
    )
    try:
        item = _command_service(request).retry_safe(
            actor=actor,
            action_id=action_id,
            expected_version=command.expected_version,
            correlation_id=str(request.state.correlation_id),
        )
    except (
        ActionConflict,
        ActionExecutionBlocked,
        ActionNotFound,
        ActionVersionConflict,
        ActorMembershipNotFound,
    ) as exc:
        raise _translate(exc) from exc
    return ActionDetailEnvelope(data=present_action_detail(item, actor=actor))


@router.post("/{action_id}/reconcile", response_model=ActionDetailEnvelope)
def reconcile_action(
    action_id: str,
    command: ReconcileActionRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ActionDetailEnvelope:
    authorize_actor(
        actor,
        Permission.ACTION_RECONCILE,
        error_code="action_reconcile_forbidden",
    )
    try:
        item = _command_service(request).reconcile(
            actor=actor,
            action_id=action_id,
            expected_version=command.expected_version,
            correlation_id=str(request.state.correlation_id),
        )
    except (
        ActionConflict,
        ActionExecutionBlocked,
        ActionNotFound,
        ActionVersionConflict,
        ActorMembershipNotFound,
    ) as exc:
        raise _translate(exc) from exc
    return ActionDetailEnvelope(data=present_action_detail(item, actor=actor))


@router.post("/{action_id}/manual-outcome", response_model=ActionDetailEnvelope)
def record_manual_outcome(
    action_id: str,
    command: RecordManualOutcomeRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ActionDetailEnvelope:
    authorize_actor(
        actor,
        Permission.ACTION_RECONCILE,
        error_code="action_reconcile_forbidden",
    )
    try:
        item = _command_service(request).record_manual_outcome(
            actor=actor,
            action_id=action_id,
            expected_version=command.expected_version,
            outcome=command.outcome,
            reason=command.reason,
            correlation_id=str(request.state.correlation_id),
        )
    except (
        ActionConflict,
        ActionNotFound,
        ActionVersionConflict,
        ActorMembershipNotFound,
    ) as exc:
        raise _translate(exc) from exc
    return ActionDetailEnvelope(data=present_action_detail(item, actor=actor))


@router.post("/{action_id}/escalate", response_model=ActionDetailEnvelope)
def escalate_action(
    action_id: str,
    command: EscalateActionRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ActionDetailEnvelope:
    authorize_actor(
        actor,
        Permission.ACTION_RECONCILE,
        error_code="action_reconcile_forbidden",
    )
    try:
        item = _command_service(request).escalate(
            actor=actor,
            action_id=action_id,
            expected_version=command.expected_version,
            reason=command.reason,
            correlation_id=str(request.state.correlation_id),
        )
    except (
        ActionConflict,
        ActionNotFound,
        ActionVersionConflict,
        ActorMembershipNotFound,
    ) as exc:
        raise _translate(exc) from exc
    return ActionDetailEnvelope(data=present_action_detail(item, actor=actor))
