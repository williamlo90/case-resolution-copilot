from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.embeddings import configured_embedding_provider
from app.api.dependencies.identity import authorize_actor, current_actor
from app.api.dependencies.policy_retrieval import configured_policy_retrieval
from app.api.errors import AppError
from app.api.schemas.common import ActorSummaryResponse
from app.api.schemas.policies import (
    CreatePolicyDraftRequest,
    CreatePolicyRequest,
    PolicyApplicabilityResponse,
    PolicyCaseReferenceResponse,
    PolicyClauseResponse,
    PolicyDetailEnvelope,
    PolicyDetailResponse,
    PolicyEvidenceEnvelope,
    PolicyEvidenceResponse,
    PolicyEvidenceResultResponse,
    PolicyListResponse,
    PolicySourceResponse,
    PolicySummaryResponse,
    PolicyVersionCommandRequest,
    PolicyVersionResponse,
    PublishPolicyVersionRequest,
    RetryPolicySourceRequest,
    SchedulePolicyVersionRequest,
)
from app.domain.identity import ActorContext, Permission
from app.domain.policies import (
    EvidenceRetrievalResult,
    EvidenceRetrievalStatus,
    GovernedPolicyVersionRecord,
    InvalidPolicyTransition,
    PolicyActorNotAssignable,
    PolicyAlreadyExists,
    PolicyApplicability,
    PolicyConcurrencyConflict,
    PolicyDraftContent,
    PolicyEvidenceBundle,
    PolicyLifecycleStatus,
    PolicyListItemRecord,
    PolicyNotFound,
    PolicySourceKind,
    PolicySourceParseError,
    PolicyVersionBundle,
    PolicyVersionConcurrencyConflict,
    PolicyWorkspaceRecord,
)
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from app.persistence.policy_repository import PolicyRepository
from app.services.policy_evidence_service import PolicyEvidenceService
from app.services.policy_service import (
    InvalidPolicyCursor,
    PolicyService,
    encode_policy_cursor,
)

router = APIRouter(tags=["policies"])

type PolicyCommand = Literal[
    "create_draft",
    "submit_review",
    "publish",
    "schedule",
    "retire",
    "retry_source",
]


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Policy data is not available.",
            status_code=503,
        )
    return database


def _repository(session: Session) -> PolicyRepository:
    return PolicyRepository(session)


def _policy_service(request: Request, session: Session) -> PolicyService:
    return PolicyService(
        _repository(session),
        configured_embedding_provider(request),
    )


def _translate(error: Exception) -> AppError:
    if isinstance(error, PolicyNotFound):
        return AppError(code="resource_not_found", message=str(error), status_code=404)
    if isinstance(error, PolicyActorNotAssignable):
        return AppError(code="policy_owner_forbidden", message=str(error), status_code=403)
    if isinstance(error, InvalidPolicyCursor):
        return AppError(code="invalid_policy_cursor", message=str(error), status_code=400)
    if isinstance(error, (PolicyConcurrencyConflict, PolicyVersionConcurrencyConflict)):
        return AppError(
            code="version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    if isinstance(error, PolicyAlreadyExists):
        return AppError(code="policy_already_exists", message=str(error), status_code=409)
    if isinstance(error, InvalidPolicyTransition):
        return AppError(code="invalid_policy_transition", message=str(error), status_code=409)
    if isinstance(error, PolicySourceParseError):
        return AppError(code="policy_source_invalid", message=str(error), status_code=422)
    return AppError(code="policy_operation_failed", message=str(error), status_code=409)


def _applicability(value: object) -> PolicyApplicability:
    return PolicyApplicability.model_validate(value)


def _summary_response(
    item: PolicyListItemRecord,
    *,
    organization_id: str,
) -> PolicySummaryResponse:
    version = item.current_version
    status = _display_status(item.policy.status, version)
    return PolicySummaryResponse(
        id=item.policy.public_id,
        organization_id=organization_id,
        title=item.policy.title,
        description=item.policy.description,
        status=status,
        owner=ActorSummaryResponse(id=item.owner.public_id, name=item.owner.name),
        applies_to=_applies_to(version),
        current_version=item.policy.current_version,
        effective_from=version.effective_from if version else None,
        effective_to=version.effective_to if version else None,
        source=PolicySourceResponse(
            kind=item.policy.source_kind.value,
            name=item.policy.source_name,
        ),
        health=_health(status),
        used_by_cases=item.used_by_cases,
        version=item.policy.version,
        updated_at=item.policy.updated_at,
    )


def _workspace_response(
    workspace: PolicyWorkspaceRecord,
    *,
    actor: ActorContext,
) -> PolicyDetailResponse:
    current_bundle = next(
        (
            bundle
            for bundle in workspace.versions
            if bundle.version.version == workspace.policy.current_version
        ),
        None,
    )
    item = PolicyListItemRecord(
        policy=workspace.policy,
        owner=workspace.owner,
        current_version=current_bundle.version if current_bundle else None,
        used_by_cases=len(
            {usage.case_public_id for bundle in workspace.versions for usage in bundle.evidence}
        ),
    )
    summary = _summary_response(item, organization_id=actor.organization_id)
    return PolicyDetailResponse(
        policy=summary,
        versions=[
            _version_response(workspace.policy.public_id, bundle) for bundle in workspace.versions
        ],
        available_commands=_available_commands(workspace, actor),
    )


def _version_response(policy_id: str, bundle: PolicyVersionBundle) -> PolicyVersionResponse:
    version = bundle.version
    return PolicyVersionResponse(
        id=version.public_id,
        policy_id=policy_id,
        version=version.version,
        record_version=version.record_version,
        status=version.status,
        immutable=version.immutable,
        created_at=version.created_at,
        published_at=version.published_at,
        effective_from=version.effective_from,
        effective_to=version.effective_to,
        applicability=PolicyApplicabilityResponse(
            decision_scope=version.decision_scope,
            case_categories=version.case_categories,
            products=version.products,
            regions=version.regions,
            channels=version.channels,
            customer_tiers=version.customer_tiers,
        ),
        source_text=version.source_text,
        clauses=[
            PolicyClauseResponse(
                id=clause.public_id,
                heading=clause.heading,
                text=clause.text,
                applies_when=clause.applies_when,
            )
            for clause in bundle.clauses
        ],
        used_by_cases=[
            PolicyCaseReferenceResponse(
                case_id=usage.case_public_id,
                citation=usage.evidence.citation,
                recorded_at=usage.evidence.recorded_at,
            )
            for usage in bundle.evidence
        ],
    )


def _evidence_response(bundle: PolicyEvidenceBundle) -> PolicyEvidenceResponse:
    evidence = bundle.evidence
    effective_date = (
        evidence.effective_from.date().isoformat()
        if evidence.effective_from is not None
        else "Immediately effective"
    )
    return PolicyEvidenceResponse(
        id=evidence.public_id,
        policy_id=bundle.policy.public_id,
        policy_version_id=bundle.version.public_id,
        policy_version=bundle.version.version,
        clause_id=bundle.clause.public_id,
        title=bundle.policy.title,
        citation=evidence.citation,
        excerpt=evidence.excerpt,
        applicability=evidence.applicability,
        effective_date=effective_date,
        freshness=evidence.freshness,
        conflict_state=evidence.conflict_state,
        fingerprint=evidence.fingerprint,
    )


def _evidence_result(result: EvidenceRetrievalResult) -> PolicyEvidenceEnvelope:
    return PolicyEvidenceEnvelope(
        data=PolicyEvidenceResultResponse(
            status=result.status,
            reason=result.reason,
            evidence=[_evidence_response(bundle) for bundle in result.evidence],
        )
    )


def _display_status(
    status: PolicyLifecycleStatus,
    version: GovernedPolicyVersionRecord | None,
) -> PolicyLifecycleStatus:
    if version is not None:
        effective_to = version.effective_to
        if (
            status in {PolicyLifecycleStatus.PUBLISHED, PolicyLifecycleStatus.SCHEDULED}
            and effective_to is not None
            and effective_to <= datetime.now(UTC)
        ):
            return PolicyLifecycleStatus.EXPIRED
    return status


def _applies_to(version: GovernedPolicyVersionRecord | None) -> list[str]:
    if version is None:
        return ["Source repair required"]
    categories = version.case_categories
    labels = {
        "billing_dispute": "Billing disputes",
        "refund_request": "Refund requests",
        "account_access": "Account access",
        "service_exception": "Service exceptions",
        "all": "All case categories",
    }
    return [
        labels.get(str(category), str(category).replace("_", " ").title())
        for category in categories
    ]


def _health(
    status: PolicyLifecycleStatus,
) -> Literal["healthy", "review_due", "conflict", "expired", "source_error"]:
    if status is PolicyLifecycleStatus.PARSING_FAILED:
        return "source_error"
    if status is PolicyLifecycleStatus.CONFLICTING:
        return "conflict"
    if status is PolicyLifecycleStatus.EXPIRED:
        return "expired"
    if status in {PolicyLifecycleStatus.DRAFT, PolicyLifecycleStatus.IN_REVIEW}:
        return "review_due"
    return "healthy"


def _available_commands(
    workspace: PolicyWorkspaceRecord, actor: ActorContext
) -> list[PolicyCommand]:
    if not actor.can(Permission.POLICY_MANAGE):
        return []
    status = workspace.policy.status
    if status is PolicyLifecycleStatus.PARSING_FAILED:
        return ["retry_source"]
    if status is PolicyLifecycleStatus.DRAFT:
        return ["submit_review"]
    if status is PolicyLifecycleStatus.IN_REVIEW:
        return ["publish", "schedule"]
    if status in {PolicyLifecycleStatus.PUBLISHED, PolicyLifecycleStatus.SCHEDULED}:
        return ["create_draft", "retire"]
    if status in {
        PolicyLifecycleStatus.RETIRED,
        PolicyLifecycleStatus.EXPIRED,
        PolicyLifecycleStatus.CONFLICTING,
    }:
        return ["create_draft"]
    return []


def _run_policy_command(
    operation: Callable[[], PolicyWorkspaceRecord], actor: ActorContext
) -> PolicyDetailEnvelope:
    try:
        workspace = operation()
    except (
        InvalidPolicyTransition,
        PolicyActorNotAssignable,
        PolicyAlreadyExists,
        PolicyConcurrencyConflict,
        PolicyNotFound,
        PolicySourceParseError,
        PolicyVersionConcurrencyConflict,
    ) as exc:
        raise _translate(exc) from exc
    return PolicyDetailEnvelope(data=_workspace_response(workspace, actor=actor))


@router.get("/api/policies", response_model=PolicyListResponse)
def list_policies(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    status: Annotated[PolicyLifecycleStatus | None, Query()] = None,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PolicyListResponse:
    authorize_actor(actor, Permission.POLICY_READ, error_code="policy_read_forbidden")
    try:
        with _database(request).session() as session:
            page = _policy_service(request, session).list_policies(
                actor=actor,
                status=status,
                query=query,
                cursor=cursor,
                limit=limit,
            )
    except (InvalidPolicyCursor, PolicyNotFound) as exc:
        raise _translate(exc) from exc
    items = [_summary_response(item, organization_id=actor.organization_id) for item in page.items]
    return PolicyListResponse(
        items=items,
        next_cursor=encode_policy_cursor(
            page.next_offset,
            status=status,
            query=query,
        ),
        total=page.total,
    )


@router.get("/api/policies/{policy_id}", response_model=PolicyDetailEnvelope)
def get_policy(
    policy_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyDetailEnvelope:
    authorize_actor(actor, Permission.POLICY_READ, error_code="policy_read_forbidden")
    try:
        with _database(request).session() as session:
            workspace = _policy_service(request, session).get_policy(
                actor=actor,
                policy_id=policy_id,
            )
    except PolicyNotFound as exc:
        raise _translate(exc) from exc
    return PolicyDetailEnvelope(data=_workspace_response(workspace, actor=actor))


@router.post("/api/policies", response_model=PolicyDetailEnvelope, status_code=201)
def create_policy(
    command: CreatePolicyRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyDetailEnvelope:
    authorize_actor(actor, Permission.POLICY_MANAGE, error_code="policy_manage_forbidden")
    with _database(request).session() as session:
        service = _policy_service(request, session)
        return _run_policy_command(
            lambda: service.create_policy(
                actor=actor,
                title=command.title,
                description=command.description,
                source_kind=PolicySourceKind(command.source.kind),
                source_name=command.source.name,
                source_text=command.source_text,
                applicability=(
                    _applicability(command.applicability.model_dump())
                    if command.applicability is not None
                    else None
                ),
                effective_from=command.effective_from,
                effective_to=command.effective_to,
                public_id=command.public_id,
                correlation_id=str(request.state.correlation_id),
            ),
            actor,
        )


@router.post(
    "/api/policies/{policy_id}/versions",
    response_model=PolicyDetailEnvelope,
    status_code=201,
)
def create_policy_draft(
    policy_id: str,
    command: CreatePolicyDraftRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyDetailEnvelope:
    authorize_actor(actor, Permission.POLICY_MANAGE, error_code="policy_manage_forbidden")
    content = PolicyDraftContent(
        source_text=command.source_text,
        applicability=_applicability(command.applicability.model_dump()),
        effective_from=command.effective_from,
        effective_to=command.effective_to,
    )
    with _database(request).session() as session:
        service = _policy_service(request, session)
        return _run_policy_command(
            lambda: service.create_draft(
                actor=actor,
                policy_id=policy_id,
                expected_policy_version=command.expected_policy_version,
                content=content,
                correlation_id=str(request.state.correlation_id),
            ),
            actor,
        )


@router.post(
    "/api/policies/{policy_id}/versions/{version}/submit-review",
    response_model=PolicyDetailEnvelope,
)
def submit_policy_review(
    policy_id: str,
    version: int,
    command: PolicyVersionCommandRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyDetailEnvelope:
    authorize_actor(actor, Permission.POLICY_MANAGE, error_code="policy_manage_forbidden")
    with _database(request).session() as session:
        service = _policy_service(request, session)
        return _run_policy_command(
            lambda: service.submit_review(
                actor=actor,
                policy_id=policy_id,
                version_number=version,
                expected_policy_version=command.expected_policy_version,
                expected_version=command.expected_version,
                correlation_id=str(request.state.correlation_id),
            ),
            actor,
        )


@router.post(
    "/api/policies/{policy_id}/versions/{version}/publish",
    response_model=PolicyDetailEnvelope,
)
def publish_policy(
    policy_id: str,
    version: int,
    command: PublishPolicyVersionRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyDetailEnvelope:
    authorize_actor(actor, Permission.POLICY_MANAGE, error_code="policy_manage_forbidden")
    with _database(request).session() as session:
        service = _policy_service(request, session)
        return _run_policy_command(
            lambda: service.publish(
                actor=actor,
                policy_id=policy_id,
                version_number=version,
                expected_policy_version=command.expected_policy_version,
                expected_version=command.expected_version,
                effective_from=command.effective_from,
                correlation_id=str(request.state.correlation_id),
            ),
            actor,
        )


@router.post(
    "/api/policies/{policy_id}/versions/{version}/schedule",
    response_model=PolicyDetailEnvelope,
)
def schedule_policy(
    policy_id: str,
    version: int,
    command: SchedulePolicyVersionRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyDetailEnvelope:
    authorize_actor(actor, Permission.POLICY_MANAGE, error_code="policy_manage_forbidden")
    with _database(request).session() as session:
        service = _policy_service(request, session)
        return _run_policy_command(
            lambda: service.schedule(
                actor=actor,
                policy_id=policy_id,
                version_number=version,
                expected_policy_version=command.expected_policy_version,
                expected_version=command.expected_version,
                effective_from=command.effective_from,
                correlation_id=str(request.state.correlation_id),
            ),
            actor,
        )


@router.post(
    "/api/policies/{policy_id}/versions/{version}/retire",
    response_model=PolicyDetailEnvelope,
)
def retire_policy(
    policy_id: str,
    version: int,
    command: PolicyVersionCommandRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyDetailEnvelope:
    authorize_actor(actor, Permission.POLICY_MANAGE, error_code="policy_manage_forbidden")
    with _database(request).session() as session:
        service = _policy_service(request, session)
        return _run_policy_command(
            lambda: service.retire(
                actor=actor,
                policy_id=policy_id,
                version_number=version,
                expected_policy_version=command.expected_policy_version,
                expected_version=command.expected_version,
                correlation_id=str(request.state.correlation_id),
            ),
            actor,
        )


@router.post(
    "/api/policies/{policy_id}/retry-source",
    response_model=PolicyDetailEnvelope,
)
def retry_policy_source(
    policy_id: str,
    command: RetryPolicySourceRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyDetailEnvelope:
    authorize_actor(actor, Permission.POLICY_MANAGE, error_code="policy_manage_forbidden")
    content = PolicyDraftContent(
        source_text=command.source_text,
        applicability=_applicability(command.applicability.model_dump()),
        effective_from=command.effective_from,
        effective_to=command.effective_to,
    )
    with _database(request).session() as session:
        service = _policy_service(request, session)
        return _run_policy_command(
            lambda: service.retry_source(
                actor=actor,
                policy_id=policy_id,
                expected_policy_version=command.expected_policy_version,
                content=content,
                correlation_id=str(request.state.correlation_id),
            ),
            actor,
        )


@router.get(
    "/api/cases/{case_id}/policy-evidence",
    response_model=PolicyEvidenceEnvelope,
)
def list_case_policy_evidence(
    case_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyEvidenceEnvelope:
    authorize_actor(actor, Permission.CASE_READ, error_code="case_read_forbidden")
    authorize_actor(actor, Permission.POLICY_READ, error_code="policy_read_forbidden")
    try:
        with _database(request).session() as session:
            repository = _repository(session)
            evidence = PolicyEvidenceService(
                repository,
                CaseRepository(session),
                configured_embedding_provider(request),
                retrieval=configured_policy_retrieval(
                    request,
                    store=repository,
                    v1_embedding_provider=configured_embedding_provider(request),
                ),
            ).list_for_case(actor=actor, case_id=case_id)
    except PolicyNotFound as exc:
        raise _translate(exc) from exc
    result = EvidenceRetrievalResult(
        status=(EvidenceRetrievalStatus.RELEVANT if evidence else EvidenceRetrievalStatus.MISSING),
        reason=(
            "Recorded policy evidence is available."
            if evidence
            else "No policy evidence has been recorded for this case."
        ),
        evidence=evidence,
    )
    return _evidence_result(result)


@router.post(
    "/api/cases/{case_id}/policy-evidence/refresh",
    response_model=PolicyEvidenceEnvelope,
)
def refresh_case_policy_evidence(
    case_id: str,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> PolicyEvidenceEnvelope:
    authorize_actor(actor, Permission.CASE_MANAGE, error_code="case_manage_forbidden")
    authorize_actor(actor, Permission.POLICY_READ, error_code="policy_read_forbidden")
    try:
        with _database(request).session() as session:
            repository = _repository(session)
            result = PolicyEvidenceService(
                repository,
                CaseRepository(session),
                configured_embedding_provider(request),
                retrieval=configured_policy_retrieval(
                    request,
                    store=repository,
                    v1_embedding_provider=configured_embedding_provider(request),
                ),
            ).refresh_for_case(
                actor=actor,
                case_id=case_id,
                correlation_id=str(request.state.correlation_id),
            )
    except (
        PolicyConcurrencyConflict,
        PolicyNotFound,
        PolicyVersionConcurrencyConflict,
    ) as exc:
        raise _translate(exc) from exc
    return _evidence_result(result)
