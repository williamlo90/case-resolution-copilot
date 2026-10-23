import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.analysis.deterministic_decision_engine import (
    DecisionEngine,
    DeterministicDecisionEngine,
)
from app.api.dependencies.embeddings import configured_embedding_provider
from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.dependencies.policy_retrieval import configured_policy_retrieval
from app.api.errors import AppError
from app.api.presenters.decision_briefs import present_decision_brief
from app.api.schemas.decision_briefs import (
    DecisionBriefEnvelope,
    GenerateDecisionBriefRequest,
)
from app.domain.cases import CaseConcurrencyConflict
from app.domain.decision_briefs import (
    DecisionBriefRecord,
    DecisionFingerprintRetryExhausted,
    DecisionGenerationInProgress,
    DecisionGenerationLeaseLost,
    DecisionGenerationRetryExhausted,
    ProposalConcurrencyConflict,
    ProposalGenerationNotAllowed,
    ProposalNotFound,
    ProposalSnapshotMismatch,
)
from app.domain.identity import ActorContext, Permission
from app.domain.policies import (
    PolicyConcurrencyConflict,
    PolicyNotFound,
    PolicyVersionConcurrencyConflict,
)
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.decision_generation_repository import DecisionGenerationRepository
from app.persistence.policy_repository import PolicyRepository
from app.retrieval.embeddings import EmbeddingProvider
from app.services.decision_brief_service import (
    DecisionBriefGenerationPlan,
    DecisionBriefService,
)
from app.services.policy_evidence_service import PolicyEvidenceService

router = APIRouter(prefix="/api/cases/{case_id}/proposals", tags=["decision briefs"])
logger = logging.getLogger(__name__)


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Decision brief data is not available.",
            status_code=503,
        )
    return database


def _translate(error: Exception) -> AppError:
    if isinstance(error, (ProposalNotFound, PolicyNotFound)):
        return AppError(code="resource_not_found", message=str(error), status_code=404)
    if isinstance(error, (CaseConcurrencyConflict, ProposalConcurrencyConflict)):
        return AppError(
            code="version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    if isinstance(error, (PolicyConcurrencyConflict, PolicyVersionConcurrencyConflict)):
        return AppError(
            code="policy_version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    if isinstance(error, ProposalGenerationNotAllowed):
        return AppError(
            code="decision_brief_not_allowed",
            message=str(error),
            status_code=409,
        )
    if isinstance(error, ProposalSnapshotMismatch):
        return AppError(
            code="proposal_snapshot_changed",
            message=str(error),
            status_code=409,
        )
    if isinstance(error, DecisionGenerationInProgress):
        return AppError(
            code="decision_generation_in_progress",
            message=str(error),
            status_code=409,
            details={"retry_after_seconds": error.retry_after_seconds},
        )
    if isinstance(
        error,
        (DecisionGenerationRetryExhausted, DecisionFingerprintRetryExhausted),
    ):
        return AppError(
            code="decision_generation_retry_exhausted",
            message=str(error),
            status_code=409,
        )
    if isinstance(error, DecisionGenerationLeaseLost):
        return AppError(
            code="decision_generation_lease_lost",
            message=str(error),
            status_code=409,
        )
    return AppError(code="decision_brief_failed", message=str(error), status_code=409)


def _decision_engine(request: Request) -> DecisionEngine:
    return getattr(request.app.state, "decision_engine", DeterministicDecisionEngine())


def _service(request: Request) -> tuple[Database, DecisionEngine]:
    return _database(request), _decision_engine(request)


def _decision_service(
    request: Request,
    session: Session,
    engine: DecisionEngine,
    embedding_provider: EmbeddingProvider,
) -> DecisionBriefService:
    case_repository = CaseRepository(session)
    policy_repository = PolicyRepository(session)
    return DecisionBriefService(
        DecisionBriefRepository(session),
        case_repository,
        PolicyEvidenceService(
            policy_repository,
            case_repository,
            embedding_provider,
            configured_policy_retrieval(
                request,
                store=policy_repository,
                v1_embedding_provider=embedding_provider,
            ),
        ),
        engine,
        DecisionGenerationRepository(session),
    )


def _release_generation(
    *,
    request: Request,
    database: Database,
    engine: DecisionEngine,
    embedding_provider: EmbeddingProvider,
    actor: ActorContext,
    case_id: str,
    preparation: DecisionBriefGenerationPlan,
    error: Exception,
) -> None:
    try:
        with database.session() as session:
            _decision_service(
                request,
                session,
                engine,
                embedding_provider,
            ).release_generation(
                actor=actor,
                case_id=case_id,
                preparation=preparation,
                error_code=type(error).__name__,
            )
    except Exception:
        logger.exception(
            "decision_generation_release_failed",
            extra={"case_id": case_id},
        )


@router.post("", response_model=DecisionBriefEnvelope, status_code=201)
def generate_decision_brief(
    case_id: str,
    command: GenerateDecisionBriefRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> DecisionBriefEnvelope:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    authorize_actor(actor, Permission.POLICY_READ, error_code="policy_read_forbidden")
    database, engine = _service(request)
    embedding_provider = configured_embedding_provider(request)
    prepared: DecisionBriefGenerationPlan | DecisionBriefRecord | None = None
    try:
        with database.session() as session:
            prepared = _decision_service(
                request,
                session,
                engine,
                embedding_provider,
            ).prepare_generation(
                actor=actor,
                case_id=case_id,
                expected_case_version=command.expected_case_version,
                correlation_id=str(request.state.correlation_id),
            )
        if isinstance(prepared, DecisionBriefGenerationPlan):
            try:
                analysis = engine.analyze(
                    workspace=prepared.workspace,
                    evidence=prepared.evidence,
                    input_fingerprint=prepared.input_fingerprint,
                )
                with database.session() as session:
                    brief = _decision_service(
                        request,
                        session,
                        engine,
                        embedding_provider,
                    ).persist_generation(
                        actor=actor,
                        case_id=case_id,
                        preparation=prepared,
                        analysis=analysis,
                        correlation_id=str(request.state.correlation_id),
                    )
            except Exception as exc:
                _release_generation(
                    request=request,
                    database=database,
                    engine=engine,
                    embedding_provider=embedding_provider,
                    actor=actor,
                    case_id=case_id,
                    preparation=prepared,
                    error=exc,
                )
                raise
        else:
            brief = prepared
    except (
        CaseConcurrencyConflict,
        PolicyConcurrencyConflict,
        PolicyNotFound,
        PolicyVersionConcurrencyConflict,
        ProposalConcurrencyConflict,
        ProposalGenerationNotAllowed,
        ProposalNotFound,
        ProposalSnapshotMismatch,
        DecisionFingerprintRetryExhausted,
        DecisionGenerationInProgress,
        DecisionGenerationLeaseLost,
        DecisionGenerationRetryExhausted,
    ) as exc:
        raise _translate(exc) from exc
    return DecisionBriefEnvelope(
        data=present_decision_brief(
            brief,
            organization_id=actor.organization_id,
            case_id=case_id,
        )
    )


@router.get("/current", response_model=DecisionBriefEnvelope)
def get_current_decision_brief(
    case_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> DecisionBriefEnvelope:
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    try:
        with _database(request).session() as session:
            brief = _decision_service(
                request,
                session,
                _decision_engine(request),
                configured_embedding_provider(request),
            ).get_latest(
                actor=actor,
                case_id=case_id,
            )
    except ProposalNotFound as exc:
        raise _translate(exc) from exc
    return DecisionBriefEnvelope(
        data=present_decision_brief(
            brief,
            organization_id=actor.organization_id,
            case_id=case_id,
        )
    )


@router.get("/{version}", response_model=DecisionBriefEnvelope)
def get_decision_brief_version(
    case_id: str,
    version: int,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> DecisionBriefEnvelope:
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    try:
        with _database(request).session() as session:
            brief = _decision_service(
                request,
                session,
                _decision_engine(request),
                configured_embedding_provider(request),
            ).get_version(
                actor=actor,
                case_id=case_id,
                version=version,
            )
    except ProposalNotFound as exc:
        raise _translate(exc) from exc
    return DecisionBriefEnvelope(
        data=present_decision_brief(
            brief,
            organization_id=actor.organization_id,
            case_id=case_id,
        )
    )
