import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.middleware import CORRELATION_HEADER

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_payload(
    *,
    code: str,
    message: str,
    correlation_id: str,
    details: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
            "details": details or {},
        }
    }


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "unavailable"))


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    correlation_id = _correlation_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        headers={CORRELATION_HEADER: correlation_id},
        content=error_payload(
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            details=exc.details,
        ),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    correlation_id = _correlation_id(request)
    safe_details = [
        {
            "location": [str(part) for part in error["loc"]],
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        headers={CORRELATION_HEADER: correlation_id},
        content=error_payload(
            code="request_validation_failed",
            message="The request did not satisfy the API contract.",
            correlation_id=correlation_id,
            details=safe_details,
        ),
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    correlation_id = _correlation_id(request)
    message = (
        str(exc.detail) if isinstance(exc.detail, str) else "The request could not be completed."
    )
    return JSONResponse(
        status_code=exc.status_code,
        headers={CORRELATION_HEADER: correlation_id},
        content=error_payload(
            code="resource_not_found" if exc.status_code == 404 else "http_error",
            message=message,
            correlation_id=correlation_id,
        ),
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = _correlation_id(request)
    logger.error(
        "unexpected_request_failure",
        extra={"correlation_id": correlation_id, "error_type": type(exc).__name__},
    )
    return JSONResponse(
        status_code=500,
        headers={CORRELATION_HEADER: correlation_id},
        content=error_payload(
            code="internal_error",
            message="The request could not be completed.",
            correlation_id=correlation_id,
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unexpected_error_handler)
