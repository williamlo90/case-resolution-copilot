from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool


class LiveResponse(BaseModel):
    status: Literal["alive"]
    service: str


class DependencyStatus(BaseModel):
    status: Literal["healthy", "not_configured", "unavailable"]


class ReadyDependencies(BaseModel):
    database: DependencyStatus


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str
    dependencies: ReadyDependencies


def create_health_router(
    service_name: str, database_check: Callable[[], bool] | None = None
) -> APIRouter:
    router = APIRouter(prefix="/api/health", tags=["health"])

    @router.get("/live", response_model=LiveResponse)
    async def live() -> LiveResponse:
        return LiveResponse(status="alive", service=service_name)

    @router.get(
        "/ready",
        response_model=ReadyResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadyResponse}},
    )
    async def ready(response: Response) -> ReadyResponse:
        if database_check is None:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ReadyResponse(
                status="not_ready",
                service=service_name,
                dependencies=ReadyDependencies(database=DependencyStatus(status="not_configured")),
            )

        database_ready = await run_in_threadpool(database_check)
        if not database_ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(
            status="ready" if database_ready else "not_ready",
            service=service_name,
            dependencies=ReadyDependencies(
                database=DependencyStatus(status="healthy" if database_ready else "unavailable")
            ),
        )

    return router
