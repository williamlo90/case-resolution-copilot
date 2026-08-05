from time import perf_counter
from typing import Annotated

from fastapi import Header, Request
from sqlalchemy.orm import Session

from app.api.errors import AppError
from app.api.middleware import add_server_timing
from app.domain.identity import ActorContext, Permission
from app.security.authentication import (
    AuthenticationRequired,
    AuthenticationUnavailable,
    AuthProvider,
    WorkspaceAccessDenied,
    WorkspaceSelectionRequired,
)
from app.security.authorization import PermissionDenied, require_permission


def authenticate_actor(
    request: Request,
    x_actor_id: str | None,
    *,
    session: Session | None = None,
) -> ActorContext:
    provider: AuthProvider = request.app.state.auth_provider
    started_at = perf_counter()
    try:
        if session is None:
            return provider.authenticate(x_actor_id, request=request)
        return provider.authenticate(
            x_actor_id,
            request=request,
            session=session,
        )
    except AuthenticationRequired as exc:
        raise AppError(
            code="authentication_required",
            message="A valid identity is required.",
            status_code=401,
        ) from exc
    except WorkspaceAccessDenied as exc:
        raise AppError(
            code="workspace_access_denied",
            message="Your account does not have access to an active workspace.",
            status_code=403,
        ) from exc
    except WorkspaceSelectionRequired as exc:
        raise AppError(
            code="workspace_selection_required",
            message="Choose one workspace before continuing.",
            status_code=409,
        ) from exc
    except AuthenticationUnavailable as exc:
        raise AppError(
            code="authentication_unavailable",
            message="Authentication is not available.",
            status_code=503,
        ) from exc
    finally:
        add_server_timing(
            request,
            "auth",
            (perf_counter() - started_at) * 1000,
        )


def current_actor(
    request: Request,
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-ID")] = None,
) -> ActorContext:
    return authenticate_actor(request, x_actor_id)


def authorize_actor(
    actor: ActorContext,
    permission: Permission,
    *,
    error_code: str = "permission_denied",
) -> None:
    try:
        require_permission(actor, permission)
    except PermissionDenied as exc:
        raise AppError(code=error_code, message=str(exc), status_code=403) from exc
