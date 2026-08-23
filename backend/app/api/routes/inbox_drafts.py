from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies.identity import current_actor
from app.api.errors import AppError
from app.api.inbox_support import INBOX_HANDLED_ERRORS, inbox_error, inbox_runtime
from app.api.schemas.inbox import (
    DraftDeliveryCommand,
    DraftDeliveryData,
    DraftDeliveryEnvelope,
    DraftDeliveryLookupEnvelope,
)
from app.domain.identity import ActorContext
from app.domain.inbox import DraftDeliveryRecord

router = APIRouter(tags=["connected inbox drafts"])


def _require_draft_writeback(request: Request) -> None:
    if not request.app.state.settings.inbox_draft_writeback_enabled:
        raise AppError(
            code="inbox_draft_writeback_disabled",
            message="Connected inbox draft creation is not enabled.",
            status_code=503,
        )


def _delivery_data(result: DraftDeliveryRecord) -> DraftDeliveryData:
    return DraftDeliveryData(
        id=result.public_id,
        status=result.status,
        attempt_count=result.attempt_count,
        provider_draft_id=result.provider_draft_id,
        last_error_code=result.last_error_code,
    )


@router.get(
    "/api/cases/{case_id}/response-draft/delivery",
    response_model=DraftDeliveryLookupEnvelope,
)
def get_latest_response_draft_delivery(
    case_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    draft_version: int = Query(ge=1),
) -> DraftDeliveryLookupEnvelope:
    try:
        result = inbox_runtime(request).drafts.latest(
            actor=actor,
            case_id=case_id,
            expected_draft_version=draft_version,
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return DraftDeliveryLookupEnvelope(
        data=_delivery_data(result) if result is not None else None
    )


@router.post(
    "/api/cases/{case_id}/response-draft/deliver",
    response_model=DraftDeliveryEnvelope,
)
def deliver_response_draft(
    case_id: str,
    command: DraftDeliveryCommand,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> DraftDeliveryEnvelope:
    _require_draft_writeback(request)
    try:
        result = inbox_runtime(request).drafts.deliver(
            actor=actor,
            case_id=case_id,
            expected_draft_version=command.expected_draft_version,
            worker_id=str(request.state.correlation_id),
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return DraftDeliveryEnvelope(
        data=_delivery_data(result.delivery)
    )


@router.post(
    "/api/draft-deliveries/{delivery_id}/reconcile",
    response_model=DraftDeliveryEnvelope,
)
def reconcile_response_draft(
    delivery_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> DraftDeliveryEnvelope:
    _require_draft_writeback(request)
    try:
        result = inbox_runtime(request).drafts.reconcile(
            actor=actor,
            delivery_id=delivery_id,
        )
    except INBOX_HANDLED_ERRORS as exc:
        raise inbox_error(exc) from exc
    return DraftDeliveryEnvelope(
        data=_delivery_data(result.delivery)
    )
