from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.errors import AppError
from app.api.presenters.quality import (
    present_quality_dashboard,
    present_quality_evidence,
)
from app.api.schemas.quality import (
    CaseQualityEnvelope,
    CaseQualityResponse,
    QualityDashboardEnvelope,
)
from app.domain.identity import ActorContext, Permission
from app.domain.quality import (
    QualityCategory,
    QualityConflict,
    QualityProjectionNotFound,
)
from app.persistence.database import Database
from app.persistence.quality_repository import QualityRepository
from app.services.quality_service import QualityService

router = APIRouter(prefix="/api/quality", tags=["quality"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Quality evidence is not available.",
            status_code=503,
        )
    return database


def _translate(error: Exception) -> AppError:
    if isinstance(error, QualityProjectionNotFound):
        return AppError(
            code="quality_case_not_found",
            message=str(error),
            status_code=404,
        )
    return AppError(
        code="quality_unavailable",
        message=str(error),
        status_code=503,
    )


@router.get("", response_model=QualityDashboardEnvelope)
def get_quality_dashboard(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    category: QualityCategory | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> QualityDashboardEnvelope:
    authorize_actor(
        actor,
        Permission.QUALITY_READ,
        error_code="quality_read_forbidden",
    )
    try:
        with _database(request).session() as session:
            record = QualityService(QualityRepository(session)).dashboard(
                actor=actor,
                category=category,
                limit=limit,
            )
    except QualityConflict as exc:
        raise _translate(exc) from exc
    return QualityDashboardEnvelope(
        data=present_quality_dashboard(
            record,
            organization_id=actor.organization_id,
        )
    )


@router.get("/cases/{case_id}", response_model=CaseQualityEnvelope)
def get_case_quality(
    case_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> CaseQualityEnvelope:
    authorize_actor(
        actor,
        Permission.QUALITY_READ,
        error_code="quality_read_forbidden",
    )
    try:
        with _database(request).session() as session:
            records = QualityService(QualityRepository(session)).get_case(
                actor=actor,
                case_id=case_id,
            )
    except QualityProjectionNotFound as exc:
        raise _translate(exc) from exc
    return CaseQualityEnvelope(
        data=CaseQualityResponse(
            organization_id=actor.organization_id,
            case_id=case_id,
            evidence=[
                present_quality_evidence(
                    record,
                    organization_id=actor.organization_id,
                )
                for record in records
            ],
        )
    )
