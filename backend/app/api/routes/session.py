from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.identity import current_actor
from app.api.errors import AppError
from app.api.schemas.organizations import (
    SessionActorResponse,
    SessionOrganizationResponse,
    SessionResponse,
)
from app.domain.identity import ActorContext, Permission
from app.security.authorization import PermissionDenied, require_permission

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("", response_model=SessionResponse)
def get_session(actor: Annotated[ActorContext, Depends(current_actor)]) -> SessionResponse:
    try:
        require_permission(actor, Permission.SESSION_READ)
    except PermissionDenied as exc:
        raise AppError(code="session_forbidden", message=str(exc), status_code=403) from exc
    return SessionResponse(
        data=SessionActorResponse(
            id=actor.actor_id,
            organization_id=actor.organization_id,
            name=actor.name,
            kind=actor.kind,
            role=actor.role,
            permissions=sorted(actor.permissions, key=lambda item: item.value),
            authentication_mode=actor.authentication_mode,
            organization=(
                SessionOrganizationResponse(
                    id=actor.organization.id,
                    name=actor.organization.name,
                    slug=actor.organization.slug,
                    version=actor.organization.version,
                    locale=actor.organization.locale,
                    time_zone=actor.organization.time_zone,
                )
                if actor.organization is not None
                else None
            ),
        )
    )
