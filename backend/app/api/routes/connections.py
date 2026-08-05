from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.errors import AppError
from app.api.presenters.connections import (
    present_connection,
    present_health_result,
)
from app.api.schemas.connections import (
    ConnectionDetailEnvelope,
    ConnectionHealthEnvelope,
    ConnectionListResponse,
    TestConnectionRequest,
)
from app.domain.connections import (
    ConnectionConflict,
    ConnectionHealth,
    ConnectionNotFound,
    ConnectionVersionConflict,
    InvalidConnectionCursor,
)
from app.domain.identity import (
    ActorContext,
    ActorMembershipNotFound,
    Permission,
)
from app.integrations.action_gateway import ActionGateway
from app.persistence.connection_repository import ConnectionRepository
from app.persistence.database import Database
from app.services.connection_service import (
    ConnectionCommandService,
    ConnectionQueryService,
)

router = APIRouter(prefix="/api/connections", tags=["connections"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Connection data is not available.",
            status_code=503,
        )
    return database


def _gateway(request: Request) -> ActionGateway:
    gateway: ActionGateway | None = request.app.state.action_gateway
    if gateway is None:
        raise AppError(
            code="action_gateway_not_configured",
            message="Connection checks are not available.",
            status_code=503,
        )
    return gateway


def _query_service(session: Session) -> ConnectionQueryService:
    return ConnectionQueryService(ConnectionRepository(session))


def _translate(error: Exception) -> AppError:
    if isinstance(error, ConnectionNotFound):
        return AppError(
            code="connection_not_found",
            message=str(error),
            status_code=404,
        )
    if isinstance(error, ActorMembershipNotFound):
        return AppError(
            code="active_membership_required",
            message=str(error),
            status_code=403,
        )
    if isinstance(error, InvalidConnectionCursor):
        return AppError(
            code="invalid_connection_cursor",
            message=str(error),
            status_code=400,
        )
    if isinstance(error, ConnectionVersionConflict):
        return AppError(
            code="version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    if isinstance(error, ConnectionConflict):
        return AppError(
            code="connection_conflict",
            message=str(error),
            status_code=409,
        )
    return AppError(
        code="connection_command_failed",
        message="The connection command could not be completed.",
        status_code=409,
    )


@router.get("", response_model=ConnectionListResponse)
def list_connections(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    health: ConnectionHealth | None = None,
    query: str | None = Query(default=None, max_length=200),
    cursor: str | None = Query(default=None, max_length=2000),
    limit: int = Query(default=50, ge=1, le=100),
) -> ConnectionListResponse:
    authorize_actor(
        actor,
        Permission.CONNECTION_READ,
        error_code="connection_read_forbidden",
    )
    try:
        with _database(request).session() as session:
            page = _query_service(session).list(
                actor=actor,
                health=health.value if health is not None else None,
                query=query,
                cursor=cursor,
                limit=limit,
            )
    except (ConnectionConflict, InvalidConnectionCursor) as exc:
        raise _translate(exc) from exc
    return ConnectionListResponse(
        items=[
            present_connection(
                connection,
                organization_id=actor.organization_id,
            )
            for connection in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@router.get("/{connection_id}", response_model=ConnectionDetailEnvelope)
def get_connection(
    connection_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ConnectionDetailEnvelope:
    authorize_actor(
        actor,
        Permission.CONNECTION_READ,
        error_code="connection_read_forbidden",
    )
    try:
        with _database(request).session() as session:
            connection = _query_service(session).get(
                actor=actor,
                connection_id=connection_id,
            )
    except ConnectionNotFound as exc:
        raise _translate(exc) from exc
    return ConnectionDetailEnvelope(
        data=present_connection(
            connection,
            organization_id=actor.organization_id,
        )
    )


@router.post("/{connection_id}/test", response_model=ConnectionHealthEnvelope)
def test_connection(
    connection_id: str,
    command: TestConnectionRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ConnectionHealthEnvelope:
    authorize_actor(
        actor,
        Permission.CONNECTION_MANAGE,
        error_code="connection_manage_forbidden",
    )
    try:
        connection, receipt = ConnectionCommandService(
            _database(request),
            _gateway(request),
        ).test(
            actor=actor,
            connection_id=connection_id,
            expected_version=command.expected_version,
            correlation_id=str(request.state.correlation_id),
        )
    except (
        ActorMembershipNotFound,
        ConnectionConflict,
        ConnectionNotFound,
        ConnectionVersionConflict,
    ) as exc:
        raise _translate(exc) from exc
    return ConnectionHealthEnvelope(
        data=present_health_result(
            connection,
            receipt,
            organization_id=actor.organization_id,
        )
    )
