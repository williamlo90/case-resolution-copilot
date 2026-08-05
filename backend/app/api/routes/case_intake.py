from typing import Annotated

from fastapi import APIRouter, Header, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.api.errors import AppError
from app.api.schemas.cases import (
    CaseIntakeReceiptResponse,
    CaseIntakeResponse,
)
from app.config import Settings
from app.domain.cases import CaseSeedConflict
from app.integrations.case_webhook import SignedCaseWebhookEvent
from app.integrations.webhook_security import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    WebhookSignatureError,
    verify_webhook,
)
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database

router = APIRouter(prefix="/api/intake", tags=["case intake"])

MAX_WEBHOOK_BYTES = 256 * 1024


async def _bounded_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_WEBHOOK_BYTES:
            raise AppError(
                code="case_payload_too_large",
                message="The case payload is too large.",
                status_code=413,
            )
    return bytes(body)


@router.post(
    "/cases",
    response_model=CaseIntakeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_case(
    request: Request,
    timestamp_header: Annotated[
        str | None,
        Header(alias=TIMESTAMP_HEADER),
    ] = None,
    signature_header: Annotated[
        str | None,
        Header(alias=SIGNATURE_HEADER),
    ] = None,
) -> CaseIntakeResponse:
    settings: Settings = request.app.state.settings
    secret = settings.case_webhook_secret_value()
    organization_id = settings.integration_organization_id
    if (
        settings.case_source_provider != "signed_webhook"
        or not secret
        or not organization_id
    ):
        raise AppError(
            code="case_intake_not_configured",
            message="Case intake is not configured.",
            status_code=503,
        )
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Case intake is not available.",
            status_code=503,
        )
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_WEBHOOK_BYTES:
        raise AppError(
            code="case_payload_too_large",
            message="The case payload is too large.",
            status_code=413,
        )
    body = await _bounded_body(request)
    try:
        verify_webhook(
            secret=secret,
            timestamp_header=timestamp_header,
            signature_header=signature_header,
            body=body,
            max_age_seconds=settings.case_webhook_max_age_seconds,
        )
    except WebhookSignatureError as exc:
        raise AppError(
            code="case_intake_unauthorized",
            message="The case intake request could not be verified.",
            status_code=401,
        ) from exc
    try:
        event = SignedCaseWebhookEvent.model_validate_json(body)
        command = event.to_case_create(organization_id=organization_id)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    try:
        with database.session() as session:
            repository = CaseRepository(session)
            correlation_id = str(request.state.correlation_id)
            workspace, created = repository.seed_case_with_status(
                organization_public_id=organization_id,
                command=command,
                correlation_id=correlation_id,
            )
            duplicate = not created
    except CaseSeedConflict as exc:
        raise AppError(
            code="case_source_conflict",
            message="This source event was already used for different case data.",
            status_code=409,
        ) from exc
    return CaseIntakeResponse(
        data=CaseIntakeReceiptResponse(
            id=workspace.case.public_id,
            source_id=workspace.case.source_id,
            duplicate=duplicate,
        )
    )
