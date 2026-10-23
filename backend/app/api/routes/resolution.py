from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.errors import AppError
from app.api.routes.cases import _database
from app.domain.cases import CaseNotFound
from app.domain.identity import ActorContext, Permission
from app.domain.resolution import LifecycleConflict
from app.persistence.resolution_repository import ResolutionRepository

router = APIRouter(prefix="/api/cases", tags=["resolution"])


class LifecycleCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    command_id: str = Field(min_length=16, max_length=128)
    kind: Literal["completed", "reopened", "escalation_routed", "escalation_acknowledged"]
    reason: str = Field(min_length=3, max_length=1000)
    reference: str | None = Field(default=None, min_length=1, max_length=200)


@router.get("/{case_id}/resolution")
def read_resolution(
    case_id: str, request: Request, actor: Annotated[ActorContext, Depends(current_actor)]
) -> dict[str, Any]:
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    try:
        with _database(request).session() as session:
            repository = ResolutionRepository(session)
            case = repository.case(actor, case_id, lock=False)
            events = repository.events(case)
            return {
                **repository.controls(actor, case, events),
                "case_id": case.public_id,
                "version": case.version,
                "status": case.status,
                "events": [
                    {
                        "id": str(e.id),
                        "kind": e.kind,
                        "at": e.occurred_at,
                        "actor_id": e.actor_id,
                        "previous_event_id": e.previous_event_id,
                        "correlation_id": e.correlation_id,
                        "data": e.data,
                    }
                    for e in events
                ],
            }
    except CaseNotFound as exc:
        raise AppError(code="case_not_found", message=str(exc), status_code=404) from exc


@router.post("/{case_id}/resolution")
def command_resolution(
    case_id: str,
    command: LifecycleCommand,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> dict[str, str]:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    if command.kind in {"completed", "escalation_acknowledged"}:
        authorize_actor(actor, Permission.REVIEW_DECIDE, error_code="review_decide_forbidden")
    try:
        with _database(request).session() as session:
            event = ResolutionRepository(session).command(
                actor=actor,
                case_id=case_id,
                correlation_id=str(request.state.correlation_id),
                **command.model_dump(),
            )
            return {"event_id": str(event.id), "kind": event.kind}
    except CaseNotFound as exc:
        raise AppError(code="case_not_found", message=str(exc), status_code=404) from exc
    except LifecycleConflict as exc:
        raise AppError(code="resolution_conflict", message=str(exc), status_code=409) from exc
