from fastapi import Request

from app.api.errors import AppError
from app.domain.inbox import (
    InboxAuthorizationError,
    InboxConflict,
    InboxCredentialUnavailable,
    InboxNotFound,
    InboxProviderUnavailable,
    InboxSyncUnavailable,
    InboxVersionConflict,
)
from app.domain.reviews import ReviewSnapshotStale
from app.runtime.inbox import InboxRuntime
from app.security.authorization import PermissionDenied

INBOX_HANDLED_ERRORS = (
    InboxAuthorizationError,
    InboxConflict,
    InboxCredentialUnavailable,
    InboxNotFound,
    InboxProviderUnavailable,
    InboxSyncUnavailable,
    InboxVersionConflict,
    PermissionDenied,
    ReviewSnapshotStale,
)


def inbox_runtime(request: Request) -> InboxRuntime:
    runtime: InboxRuntime | None = request.app.state.inbox_runtime
    if runtime is None:
        raise AppError(
            code="connected_inbox_not_configured",
            message="Connected inbox is not available.",
            status_code=503,
        )
    return runtime


def inbox_error(error: Exception) -> AppError:
    if isinstance(error, InboxNotFound):
        return AppError(code="inbox_resource_not_found", message=str(error), status_code=404)
    if isinstance(error, PermissionDenied):
        return AppError(code="inbox_permission_denied", message=str(error), status_code=403)
    if isinstance(error, InboxVersionConflict):
        return AppError(
            code="inbox_version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    if isinstance(error, ReviewSnapshotStale):
        return AppError(code="review_is_stale", message=str(error), status_code=409)
    if isinstance(error, (InboxConflict, InboxCredentialUnavailable)):
        return AppError(code="inbox_state_conflict", message=str(error), status_code=409)
    if isinstance(error, InboxAuthorizationError):
        return AppError(code="inbox_authorization_failed", message=str(error), status_code=400)
    if isinstance(error, (InboxProviderUnavailable, InboxSyncUnavailable)):
        return AppError(
            code="inbox_provider_unavailable",
            message="The connected inbox is temporarily unavailable.",
            status_code=503,
        )
    return AppError(
        code="inbox_command_failed",
        message="The inbox command could not be completed.",
        status_code=409,
    )
