"""Authenticated adapter to existing commands, restricted to owned synthetic tenants."""

from types import SimpleNamespace
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from starlette.datastructures import State

from app.api.dependencies.identity import current_actor
from app.api.errors import AppError
from app.api.presenters.cases import present_case_workspace
from app.api.presenters.decision_briefs import present_decision_brief
from app.api.routes import actions, cases, decision_briefs, policies, resolution, reviews
from app.api.schemas.actions import ExecuteActionRequest, ReconcileActionRequest
from app.api.schemas.decision_briefs import GenerateDecisionBriefRequest
from app.api.schemas.reviews import DecideReviewRequest, ReserveReviewRequest, SubmitReviewRequest
from app.domain.identity import ActorContext
from app.domain.policies import PolicyDraftContent
from app.domain.reviews import ReviewDecision
from app.persistence.case_repository import CaseRepository
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.models import CaseActionModel, CaseReviewModel
from app.retrieval.embeddings import DEFAULT_EMBEDDING_PROVIDER
from app.services.case_service import CaseService
from app.services.v2_demo import DemoRole, V2DemoSessions, demo_actor
from app.services.v2_demo_fixtures import applicability, policy_text, publish_draft

router = APIRouter(prefix="/api/demo/v2", tags=["synthetic V2 demo"])
SessionId = Annotated[str, Path(pattern=r"^VD-[A-F0-9]{16}$")]


class CreateDemo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Literal["verified_reopen", "sop_revision", "timeout_recovery"]
    command_id: str = Field(min_length=16, max_length=128)


class DemoCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    command: Literal[
        "generate",
        "submit",
        "reserve",
        "approve",
        "execute",
        "reconcile",
        "close",
        "reopen",
        "publish_revision",
        "rollback",
        "route_escalation",
        "acknowledge",
    ]
    role: DemoRole
    decision: ReviewDecision = ReviewDecision.APPROVE
    expected_version: int = Field(ge=1)
    command_id: str = Field(min_length=16, max_length=128)
    snapshot_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    reason: str = Field(min_length=3, max_length=1000)
    reference: str | None = Field(default=None, min_length=1, max_length=200)
    resource_id: str | None = Field(default=None, min_length=1, max_length=64)
    expected_proposal_version: int | None = Field(default=None, ge=1)


def _sessions(request: Request) -> V2DemoSessions:
    return V2DemoSessions(cases._database(request))


def _scoped_request(request: Request, store: V2DemoSessions, data: dict[str, Any]) -> Request:
    # A new request-local app-state container, never a mutation of shared FastAPI state.
    state = State(
        {
            "database": store.database,
            "decision_engine": request.app.state.decision_engine,
            "embedding_provider": DEFAULT_EMBEDDING_PROVIDER,
            "settings": None,  # Bounded, immediate V1 evidence index for the synthetic policy only.
            "action_gateway": store.gateway(data),
        }
    )
    return Request(dict(request.scope, app=SimpleNamespace(state=state)))


def _ids(store: V2DemoSessions, data: dict[str, Any]) -> tuple[str | None, str | None]:
    organization_id = UUID(data["organization_uuid"])
    with store.database.session() as session:
        review = session.scalar(
            select(CaseReviewModel)
            .where(CaseReviewModel.organization_id == organization_id)
            .order_by(CaseReviewModel.submitted_at.desc())
            .limit(1)
        )
        action = session.scalar(
            select(CaseActionModel)
            .where(CaseActionModel.organization_id == organization_id)
            .order_by(CaseActionModel.created_at.desc())
            .limit(1)
        )
        return review.public_id if review else None, action.public_id if action else None


def _view(request: Request, owner: ActorContext, data: dict[str, Any]) -> dict[str, Any]:
    store = _sessions(request)
    scoped = _scoped_request(request, store, data)
    actor = demo_actor(owner, data["organization_id"], "reviewer")
    review_id, action_id = _ids(store, data)
    with store.database.session() as session:
        product_workspace = present_case_workspace(
            cases._workspace_query(session).get(
                actor=demo_actor(owner, data["organization_id"], "specialist"),
                case_id=data["case_id"],
            ),
            organization_id=data["organization_id"],
        ).model_dump(mode="json")
        workspace = CaseService(CaseRepository(session)).get_case(
            actor=actor, case_id=data["case_id"]
        )
        brief = DecisionBriefRepository(session).get_latest(
            organization_public_id=actor.organization_id, case_public_id=data["case_id"]
        )
        brief_view = (
            present_decision_brief(
                brief, organization_id=actor.organization_id, case_id=data["case_id"]
            ).model_dump(mode="json")
            if brief
            else None
        )
    return {
        "workspace": product_workspace,
        "session": {k: data[k] for k in ("session_id", "scenario", "case_id", "created_at")},
        "case": {
            "id": workspace.case.public_id,
            "version": workspace.case.version,
            "status": workspace.case.status.value,
            "issue": workspace.case.issue,
            "request": workspace.request.customer_message,
            "records": [
                {"id": r.public_id, "reference": r.source_reference, "fields": r.fields}
                for r in workspace.business_contexts
            ],
        },
        "policy": policies.get_policy(data["policy_id"], scoped, actor).data.model_dump(
            mode="json"
        ),
        "brief": brief_view,
        "review": reviews.get_review(review_id, scoped, actor).data.model_dump(mode="json")
        if review_id
        else None,
        "action": actions.get_action(action_id, scoped, actor).data.model_dump(mode="json")
        if action_id
        else None,
        "target": store.gateway(data).inspect(),
        "lifecycle": resolution.read_resolution(data["case_id"], scoped, actor),
        "observations": store.observations(owner, data["session_id"]),
    }


@router.get("/sessions")
def list_sessions(
    request: Request, actor: Annotated[ActorContext, Depends(current_actor)]
) -> dict[str, Any]:
    return {
        "items": [
            {k: d[k] for k in ("session_id", "scenario", "case_id", "created_at")}
            for d in _sessions(request).list_owned(actor)
        ]
    }


@router.post("/sessions", status_code=201)
def create_session(
    command: CreateDemo, request: Request, actor: Annotated[ActorContext, Depends(current_actor)]
) -> dict[str, Any]:
    data = _sessions(request).create(
        actor, command.scenario, command.command_id, str(request.state.correlation_id)
    )
    return {"data": _view(request, actor, data)}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: SessionId, request: Request, actor: Annotated[ActorContext, Depends(current_actor)]
) -> dict[str, Any]:
    return {"data": _view(request, actor, _sessions(request).get(actor, session_id))}


def _required(value: str | None, name: str) -> str:
    if value is None:
        raise AppError(code="demo_step_missing", message=f"Complete {name} first.", status_code=409)
    return value


def _command(
    command: DemoCommand,
    scoped: Request,
    owner: ActorContext,
    store: V2DemoSessions,
    data: dict[str, Any],
) -> None:
    actor = demo_actor(owner, data["organization_id"], command.role)
    case_id = data["case_id"]
    review_id, action_id = _ids(store, data)
    selected = (
        review_id
        if command.command in {"reserve", "approve"}
        else action_id
        if command.command in {"execute", "reconcile"}
        else None
    )
    if selected is not None and command.resource_id != selected:
        raise AppError(
            code="demo_resource_changed",
            message="Selected record changed; reload first.",
            status_code=409,
        )
    if command.command == "generate":
        decision_briefs.generate_decision_brief(
            case_id,
            GenerateDecisionBriefRequest(expected_case_version=command.expected_version),
            scoped,
            actor,
        )
    elif command.command == "submit":
        brief = decision_briefs.get_current_decision_brief(case_id, scoped, actor).data
        if brief.proposal.version != command.expected_proposal_version:
            raise AppError(
                code="demo_proposal_changed",
                message="Decision Brief changed; reload first.",
                status_code=409,
            )
        reviews.submit_review(
            case_id,
            brief.proposal.version,
            SubmitReviewRequest(expected_case_version=command.expected_version),
            scoped,
            actor,
        )
    elif command.command == "reserve":
        reviews.reserve_review(
            _required(review_id, "submission"),
            ReserveReviewRequest(expected_version=command.expected_version),
            scoped,
            actor,
        )
    elif command.command == "approve":
        reviews.decide_review(
            _required(review_id, "submission"),
            DecideReviewRequest(
                expected_version=command.expected_version,
                snapshot_fingerprint=_required(command.snapshot_fingerprint, "snapshot selection"),
                decision=command.decision,
                reason=command.reason,
            ),
            scoped,
            actor,
        )
    elif command.command == "execute":
        actions.execute_action(
            _required(action_id, "approval"),
            ExecuteActionRequest(expected_version=command.expected_version),
            scoped,
            actor,
        )
    elif command.command == "reconcile":
        actions.reconcile_action(
            _required(action_id, "execution"),
            ReconcileActionRequest(expected_version=command.expected_version),
            scoped,
            actor,
        )
    elif command.command in {"publish_revision", "rollback"}:
        if data["scenario"] != "sop_revision" or command.role != "policy_manager":
            raise AppError(
                code="demo_policy_forbidden",
                message="Use the SOP scenario and policy manager role.",
                status_code=403,
            )
        # All three existing policy-service transitions commit together.
        with store.database.session() as session:
            service = policies._policy_service(scoped, session)
            current = service.get_policy(actor=actor, policy_id=data["policy_id"])
            expected = 1 if command.command == "publish_revision" else 2
            if current.policy.current_version != expected:
                raise AppError(
                    code="demo_policy_sequence",
                    message="Reload and follow the revision sequence.",
                    status_code=409,
                )
            policies._run_policy_command(
                lambda: publish_draft(
                    service,
                    service.create_draft(
                        actor=actor,
                        policy_id=data["policy_id"],
                        expected_policy_version=command.expected_version,
                        content=PolicyDraftContent(
                            source_text=policy_text(revised=command.command == "publish_revision"),
                            applicability=applicability(),
                            effective_from=None,
                            effective_to=None,
                        ),
                        correlation_id=str(scoped.state.correlation_id),
                    ),
                    actor,
                    str(scoped.state.correlation_id),
                ),
                actor,
            )
    else:
        kind = {
            "close": "completed",
            "reopen": "reopened",
            "route_escalation": "escalation_routed",
            "acknowledge": "escalation_acknowledged",
        }[command.command]
        reference = command.reference
        if command.command == "route_escalation":
            reference = demo_actor(owner, data["organization_id"], "reviewer").actor_id
        resolution.command_resolution(
            case_id,
            resolution.LifecycleCommand(
                expected_version=command.expected_version,
                command_id=command.command_id,
                kind=kind,
                reason=command.reason,
                reference=reference,
            ),
            scoped,
            actor,
        )


@router.post("/sessions/{session_id}/commands")
def run_command(
    session_id: SessionId,
    command: DemoCommand,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> dict[str, Any]:
    store = _sessions(request)
    data = store.get(actor, session_id)  # Real auth, role and ownership checked before simulation.
    scoped = _scoped_request(request, store, data)
    try:
        _command(command, scoped, actor, store, data)
    except AppError as exc:
        store.record_command(
            actor, data, command.role, command.command, exc.code, str(request.state.correlation_id)
        )
        raise
    store.record_command(
        actor, data, command.role, command.command, "accepted", str(request.state.correlation_id)
    )
    return {"data": _view(request, actor, data)}
