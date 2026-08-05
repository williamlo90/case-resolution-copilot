from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.errors import AppError
from app.api.presenters.notifications import present_notification
from app.api.schemas.notifications import (
    MarkAllNotificationsReadEnvelope,
    MarkAllNotificationsReadResponse,
    MarkNotificationReadRequest,
    NotificationDetailEnvelope,
    NotificationListResponse,
)
from app.domain.identity import ActorContext, ActorMembershipNotFound, Permission
from app.domain.notifications import (
    InvalidNotificationCursor,
    NotificationConflict,
    NotificationNotFound,
    NotificationVersionConflict,
)
from app.persistence.database import Database
from app.persistence.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Notifications are not available.",
            status_code=503,
        )
    return database


def _translate(error: Exception) -> AppError:
    if isinstance(error, NotificationNotFound):
        return AppError(
            code="notification_not_found",
            message=str(error),
            status_code=404,
        )
    if isinstance(error, ActorMembershipNotFound):
        return AppError(
            code="active_membership_required",
            message=str(error),
            status_code=403,
        )
    if isinstance(error, InvalidNotificationCursor):
        return AppError(
            code="invalid_notification_cursor",
            message=str(error),
            status_code=400,
        )
    if isinstance(error, NotificationVersionConflict):
        return AppError(
            code="version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    return AppError(
        code="notification_conflict",
        message=str(error),
        status_code=409,
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    unread_only: bool = False,
    cursor: str | None = Query(default=None, max_length=2000),
    limit: int = Query(default=30, ge=1, le=100),
) -> NotificationListResponse:
    authorize_actor(
        actor,
        Permission.SESSION_READ,
        error_code="notification_read_forbidden",
    )
    try:
        with _database(request).session() as session:
            page = NotificationService(NotificationRepository(session)).list(
                actor=actor,
                unread_only=unread_only,
                cursor=cursor,
                limit=limit,
            )
    except (
        ActorMembershipNotFound,
        InvalidNotificationCursor,
        NotificationConflict,
    ) as exc:
        raise _translate(exc) from exc
    return NotificationListResponse(
        items=[
            present_notification(item, organization_id=actor.organization_id)
            for item in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
        unread_count=page.unread_count,
    )


@router.post("/read-all", response_model=MarkAllNotificationsReadEnvelope)
def mark_all_notifications_read(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> MarkAllNotificationsReadEnvelope:
    authorize_actor(
        actor,
        Permission.SESSION_READ,
        error_code="notification_read_forbidden",
    )
    try:
        with _database(request).session() as session:
            updated = NotificationService(
                NotificationRepository(session)
            ).mark_all_read(actor=actor)
    except ActorMembershipNotFound as exc:
        raise _translate(exc) from exc
    return MarkAllNotificationsReadEnvelope(
        data=MarkAllNotificationsReadResponse(updated=updated)
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationDetailEnvelope,
)
def mark_notification_read(
    notification_id: str,
    command: MarkNotificationReadRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> NotificationDetailEnvelope:
    authorize_actor(
        actor,
        Permission.SESSION_READ,
        error_code="notification_read_forbidden",
    )
    try:
        with _database(request).session() as session:
            record = NotificationService(
                NotificationRepository(session)
            ).mark_read(
                actor=actor,
                notification_id=notification_id,
                expected_version=command.expected_version,
            )
    except (
        ActorMembershipNotFound,
        NotificationConflict,
        NotificationNotFound,
        NotificationVersionConflict,
    ) as exc:
        raise _translate(exc) from exc
    return NotificationDetailEnvelope(
        data=present_notification(record, organization_id=actor.organization_id)
    )
