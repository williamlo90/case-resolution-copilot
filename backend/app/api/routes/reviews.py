from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.embeddings import configured_embedding_provider
from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.errors import AppError
from app.api.presenters.reviews import (
    present_review_detail,
    present_review_summary,
)
from app.api.schemas.reviews import (
    DecideReviewRequest,
    ReserveReviewRequest,
    ReviewDetailEnvelope,
    ReviewListResponse,
    SubmitReviewRequest,
)
from app.domain.cases import CaseConcurrencyConflict
from app.domain.identity import (
    ActorContext,
    ActorMembershipNotFound,
    Permission,
)
from app.domain.policies import (
    PolicyConcurrencyConflict,
    PolicyNotFound,
    PolicyVersionConcurrencyConflict,
)
from app.domain.reviews import (
    InvalidReviewCursor,
    ReviewAuthorityDenied,
    ReviewConflict,
    ReviewDecisionNotAllowed,
    ReviewNotFound,
    ReviewPolicyState,
    ReviewReservationExpired,
    ReviewSnapshotStale,
    ReviewStatus,
    ReviewSubmissionNotAllowed,
    ReviewVersionConflict,
)
from app.domain.settings import SettingsConflict
from app.persistence.action_repository import ActionRepository
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.decision_brief_repository import DecisionBriefRepository
from app.persistence.policy_repository import PolicyRepository
from app.persistence.review_repository import ReviewRepository
from app.persistence.settings_repository import OrganizationSettingsRepository
from app.services.action_service import ActionMaterializationService
from app.services.policy_evidence_service import PolicyEvidenceService
from app.services.review_service import ReviewService

router = APIRouter(tags=["reviews"])


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Review data is not available.",
            status_code=503,
        )
    return database


def _service(request: Request, session: Session) -> ReviewService:
    case_repository = CaseRepository(session)
    embedding_provider = configured_embedding_provider(request)
    policy_repository = PolicyRepository(session)
    return ReviewService(
        ReviewRepository(session),
        case_repository,
        DecisionBriefRepository(session),
        policy_repository,
        PolicyEvidenceService(
            policy_repository,
            case_repository,
            embedding_provider,
        ),
        ActionMaterializationService(ActionRepository(session)),
        OrganizationSettingsRepository(session),
    )


def _translate(error: Exception) -> AppError:
    if isinstance(error, (ReviewNotFound, PolicyNotFound)):
        return AppError(code="resource_not_found", message=str(error), status_code=404)
    if isinstance(error, ActorMembershipNotFound):
        return AppError(
            code="active_membership_required",
            message=str(error),
            status_code=403,
        )
    if isinstance(error, ReviewAuthorityDenied):
        return AppError(
            code="review_authority_denied",
            message=str(error),
            status_code=403,
        )
    if isinstance(error, InvalidReviewCursor):
        return AppError(
            code="invalid_review_cursor",
            message=str(error),
            status_code=400,
        )
    if isinstance(error, (CaseConcurrencyConflict, ReviewVersionConflict)):
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
    if isinstance(error, ReviewSnapshotStale):
        return AppError(
            code="review_snapshot_stale",
            message=str(error),
            status_code=409,
        )
    if isinstance(error, ReviewReservationExpired):
        return AppError(
            code="review_reservation_expired",
            message=str(error),
            status_code=409,
        )
    if isinstance(error, ReviewDecisionNotAllowed):
        return AppError(
            code="review_decision_not_allowed",
            message=str(error),
            status_code=409,
        )
    if isinstance(error, ReviewSubmissionNotAllowed):
        return AppError(
            code="review_submission_not_allowed",
            message=str(error),
            status_code=409,
        )
    if isinstance(error, ReviewConflict):
        return AppError(code="review_conflict", message=str(error), status_code=409)
    if isinstance(error, SettingsConflict):
        return AppError(
            code="review_settings_unavailable",
            message="Review rules are not available.",
            status_code=503,
        )
    return AppError(
        code="review_failed",
        message="The review command could not be completed.",
        status_code=409,
    )


@router.post(
    "/api/cases/{case_id}/proposals/{proposal_version}/reviews",
    response_model=ReviewDetailEnvelope,
    status_code=201,
)
def submit_review(
    case_id: str,
    proposal_version: Annotated[int, Path(ge=1)],
    command: SubmitReviewRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ReviewDetailEnvelope:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    authorize_actor(actor, Permission.REVIEW_READ, error_code="review_read_forbidden")
    try:
        with _database(request).session() as session:
            detail = _service(request, session).submit(
                actor=actor,
                case_id=case_id,
                proposal_version=proposal_version,
                expected_case_version=command.expected_case_version,
                correlation_id=str(request.state.correlation_id),
            )
    except (
        ActorMembershipNotFound,
        CaseConcurrencyConflict,
        PolicyConcurrencyConflict,
        PolicyNotFound,
        PolicyVersionConcurrencyConflict,
        ReviewConflict,
        ReviewNotFound,
        ReviewSnapshotStale,
        ReviewSubmissionNotAllowed,
        ReviewVersionConflict,
        SettingsConflict,
    ) as exc:
        raise _translate(exc) from exc
    return ReviewDetailEnvelope(
        data=present_review_detail(
            detail,
            organization_id=actor.organization_id,
            now=datetime.now(UTC),
        )
    )


@router.get("/api/reviews", response_model=ReviewListResponse)
def list_reviews(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    status: ReviewStatus | None = None,
    policy_state: ReviewPolicyState | None = None,
    query: str | None = Query(default=None, max_length=200),
    cursor: str | None = Query(default=None, max_length=2000),
    limit: int = Query(default=50, ge=1, le=100),
) -> ReviewListResponse:
    authorize_actor(actor, Permission.REVIEW_READ, error_code="review_read_forbidden")
    try:
        with _database(request).session() as session:
            page = _service(request, session).list(
                actor=actor,
                status=status.value if status is not None else None,
                policy_state=(policy_state.value if policy_state is not None else None),
                query=query,
                cursor=cursor,
                limit=limit,
            )
    except (InvalidReviewCursor, ReviewConflict) as exc:
        raise _translate(exc) from exc
    now = datetime.now(UTC)
    return ReviewListResponse(
        items=[
            present_review_summary(
                item,
                organization_id=actor.organization_id,
                now=now,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@router.get("/api/reviews/{review_id}", response_model=ReviewDetailEnvelope)
def get_review(
    review_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ReviewDetailEnvelope:
    authorize_actor(actor, Permission.REVIEW_READ, error_code="review_read_forbidden")
    try:
        with _database(request).session() as session:
            detail = _service(request, session).get(actor=actor, review_id=review_id)
    except (ReviewNotFound, SettingsConflict) as exc:
        raise _translate(exc) from exc
    return ReviewDetailEnvelope(
        data=present_review_detail(
            detail,
            organization_id=actor.organization_id,
            now=datetime.now(UTC),
        )
    )


@router.post(
    "/api/reviews/{review_id}/reserve",
    response_model=ReviewDetailEnvelope,
)
def reserve_review(
    review_id: str,
    command: ReserveReviewRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ReviewDetailEnvelope:
    authorize_actor(actor, Permission.REVIEW_RESERVE, error_code="review_reserve_forbidden")
    try:
        with _database(request).session() as session:
            detail = _service(request, session).reserve(
                actor=actor,
                review_id=review_id,
                expected_version=command.expected_version,
                correlation_id=str(request.state.correlation_id),
            )
    except (
        ActorMembershipNotFound,
        ReviewAuthorityDenied,
        ReviewConflict,
        ReviewNotFound,
        ReviewSnapshotStale,
        ReviewVersionConflict,
        SettingsConflict,
    ) as exc:
        raise _translate(exc) from exc
    return ReviewDetailEnvelope(
        data=present_review_detail(
            detail,
            organization_id=actor.organization_id,
            now=datetime.now(UTC),
        )
    )


@router.post(
    "/api/reviews/{review_id}/decisions",
    response_model=ReviewDetailEnvelope,
)
def decide_review(
    review_id: str,
    command: DecideReviewRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> ReviewDetailEnvelope:
    authorize_actor(actor, Permission.REVIEW_DECIDE, error_code="review_decide_forbidden")
    try:
        with _database(request).session() as session:
            detail = _service(request, session).decide(
                actor=actor,
                review_id=review_id,
                expected_version=command.expected_version,
                snapshot_fingerprint=command.snapshot_fingerprint,
                decision=command.decision,
                reason=command.reason,
                correlation_id=str(request.state.correlation_id),
            )
    except (
        ActorMembershipNotFound,
        ReviewAuthorityDenied,
        ReviewConflict,
        ReviewDecisionNotAllowed,
        ReviewNotFound,
        ReviewReservationExpired,
        ReviewSnapshotStale,
        ReviewVersionConflict,
        SettingsConflict,
    ) as exc:
        raise _translate(exc) from exc
    return ReviewDetailEnvelope(
        data=present_review_detail(
            detail,
            organization_id=actor.organization_id,
            now=datetime.now(UTC),
        )
    )
