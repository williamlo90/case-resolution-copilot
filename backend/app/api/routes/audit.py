from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.errors import AppError
from app.api.presenters.audit import present_case_audit_export
from app.api.schemas.audit import CaseAuditExportEnvelope
from app.domain.audit import CaseAuditNotFound
from app.domain.identity import ActorContext, ActorMembershipNotFound, Permission
from app.persistence.audit_repository import CaseAuditRepository
from app.persistence.database import Database
from app.services.audit_service import CaseAuditService

router = APIRouter(tags=["audit"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Case audit records are not available.",
            status_code=503,
        )
    return database


def _translate(error: Exception) -> AppError:
    if isinstance(error, CaseAuditNotFound):
        return AppError(
            code="case_audit_not_found",
            message=str(error),
            status_code=404,
        )
    return AppError(
        code="active_membership_required",
        message=str(error),
        status_code=403,
    )


@router.post(
    "/api/cases/{case_id}/audit-export",
    response_model=CaseAuditExportEnvelope,
)
def export_case_audit(
    case_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> CaseAuditExportEnvelope:
    authorize_actor(
        actor,
        Permission.AUDIT_READ,
        error_code="audit_read_forbidden",
    )
    try:
        with _database(request).session() as session:
            record = CaseAuditService(CaseAuditRepository(session)).export(
                actor=actor,
                case_id=case_id,
                correlation_id=str(request.state.correlation_id),
            )
    except (ActorMembershipNotFound, CaseAuditNotFound) as exc:
        raise _translate(exc) from exc
    return CaseAuditExportEnvelope(data=present_case_audit_export(record))
