from hmac import compare_digest
from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.api.errors import AppError
from app.api.schemas.policy_indexing import (
    PolicyIndexDrainData,
    PolicyIndexDrainEnvelope,
)
from app.services.policy_indexing import PolicyIndexingService

router = APIRouter(prefix="/api/internal/policy-index", tags=["internal policy index"])
SCHEDULER_HEADER = "X-Policy-Index-Secret"


def _service(request: Request) -> PolicyIndexingService:
    service: PolicyIndexingService | None = request.app.state.policy_indexing_service
    if service is None:
        raise AppError(
            code="policy_indexing_disabled",
            message="Policy indexing is not enabled.",
            status_code=503,
        )
    return service


def _authenticate(request: Request, provided: str | None) -> None:
    expected = request.app.state.settings.policy_index_scheduler_secret_value()
    if expected is None or provided is None or not compare_digest(provided, expected):
        raise AppError(
            code="policy_index_scheduler_unauthorized",
            message="The policy index scheduler request could not be verified.",
            status_code=401,
        )


@router.post("/drain", response_model=PolicyIndexDrainEnvelope)
def drain_policy_index(
    request: Request,
    scheduler_secret: Annotated[str | None, Header(alias=SCHEDULER_HEADER)] = None,
) -> PolicyIndexDrainEnvelope:
    _authenticate(request, scheduler_secret)
    result = _service(request).drain(worker_id=str(request.state.correlation_id))
    return PolicyIndexDrainEnvelope(data=PolicyIndexDrainData.model_validate(result))
