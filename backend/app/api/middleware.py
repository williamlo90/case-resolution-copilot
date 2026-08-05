import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

CORRELATION_HEADER = "X-Correlation-ID"
SERVER_TIMING_HEADER = "Server-Timing"
SUPPORT_TIMING_HEADER = "X-Support-Copilot-Timing"
NO_STORE_HEADER = "no-store"
API_CONTENT_SECURITY_POLICY = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"
API_SECURITY_HEADERS = {
    "Cache-Control": NO_STORE_HEADER,
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}
_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
logger = logging.getLogger(__name__)


def add_server_timing(
    request: Request,
    metric: str,
    duration_ms: float,
) -> None:
    timings: list[tuple[str, float]] = getattr(
        request.state,
        "server_timings",
        [],
    )
    timings.append((metric, max(0.0, duration_ms)))
    request.state.server_timings = timings


def _resolve_correlation_id(candidate: str | None) -> str:
    if candidate and _VALID_CORRELATION_ID.fullmatch(candidate):
        return candidate
    return f"corr_{uuid4().hex}"


def register_http_middleware(app: FastAPI, *, production: bool = False) -> None:
    @app.middleware("http")
    async def correlation_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = _resolve_correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = correlation_id
        request.state.server_timings = []
        started_at = perf_counter()

        response = await call_next(request)
        duration_ms = (perf_counter() - started_at) * 1000
        timings: list[tuple[str, float]] = request.state.server_timings
        timings.append(("app", duration_ms))
        timing_value = ", ".join(
            f"{metric};dur={duration:.2f}"
            for metric, duration in timings
        )
        response.headers[CORRELATION_HEADER] = correlation_id
        response.headers[SERVER_TIMING_HEADER] = timing_value
        response.headers[SUPPORT_TIMING_HEADER] = timing_value
        for header, value in API_SECURITY_HEADERS.items():
            response.headers[header] = value
        if production:
            response.headers["Content-Security-Policy"] = API_CONTENT_SECURITY_POLICY
        logger.info(
            "request_completed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
