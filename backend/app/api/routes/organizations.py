import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies.identity import current_actor
from app.api.errors import AppError
from app.api.schemas.organizations import (
    CreateInvitationRequest,
    InvitationDetailResponse,
    InvitationListResponse,
    InvitationResponse,
    MemberDetailResponse,
    MemberListResponse,
    MemberResponse,
    OrganizationDetailResponse,
    OrganizationResponse,
    RevokeInvitationRequest,
    UpdateMemberRequest,
)
from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorMembershipNotFound,
    InvitationConflict,
    InvitationNotFound,
    InvitationRecord,
    InvitationVersionConflict,
    MemberConflict,
    MemberNotFound,
    MemberRecord,
    MemberStatus,
    MemberVersionConflict,
    OrganizationNotFound,
    OrganizationRecord,
    Permission,
)
from app.integrations.clerk_identity import (
    ClerkIdentityGateway,
    InvitationDeliveryUnavailable,
)
from app.persistence.database import Database
from app.persistence.identity_repository import OrganizationRepository
from app.security.authorization import PermissionDenied, require_permission
from app.services.organization_service import OrganizationService

router = APIRouter(tags=["organization"])
logger = logging.getLogger(__name__)


def _database(request: Request) -> Database:
    database: Database | None = request.app.state.database
    if database is None:
        raise AppError(
            code="database_not_configured",
            message="Organization data is not available.",
            status_code=503,
        )
    return database


def _translate(error: Exception) -> AppError:
    if isinstance(error, InvitationDeliveryUnavailable):
        return AppError(
            code="invitation_delivery_unavailable",
            message=(
                "The invitation email could not be sent. "
                "No workspace invitation was created."
            ),
            status_code=503,
        )
    if isinstance(error, PermissionDenied):
        return AppError(code="organization_forbidden", message=str(error), status_code=403)
    if isinstance(error, ActorMembershipNotFound):
        return AppError(code="membership_forbidden", message=str(error), status_code=403)
    if isinstance(error, OrganizationNotFound):
        return AppError(code="organization_not_found", message=str(error), status_code=404)
    if isinstance(error, MemberNotFound):
        return AppError(code="member_not_found", message=str(error), status_code=404)
    if isinstance(error, InvitationNotFound):
        return AppError(code="invitation_not_found", message=str(error), status_code=404)
    if isinstance(error, (MemberVersionConflict, InvitationVersionConflict)):
        return AppError(
            code="version_conflict",
            message=str(error),
            status_code=409,
            details={
                "expected_version": error.expected_version,
                "current_version": error.current_version,
            },
        )
    if isinstance(error, MemberConflict):
        return AppError(code="member_conflict", message=str(error), status_code=409)
    return AppError(code="invitation_conflict", message=str(error), status_code=409)


def _authorize(actor: ActorContext, permission: Permission) -> None:
    try:
        require_permission(actor, permission)
    except PermissionDenied as exc:
        raise _translate(exc) from exc


def _organization_response(record: OrganizationRecord) -> OrganizationResponse:
    return OrganizationResponse(
        id=record.public_id,
        name=record.name,
        slug=record.slug,
        version=record.version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _member_response(record: MemberRecord, organization_id: str) -> MemberResponse:
    role = record.role
    return MemberResponse(
        id=record.public_id,
        organization_id=organization_id,
        name=record.name,
        email=record.email,
        role=role,
        status=record.status,
        authority=sorted(permission.value for permission in ROLE_PERMISSIONS[role]),
        version=record.version,
        last_active_at=record.last_active_at,
    )


def _invitation_response(record: InvitationRecord, organization_id: str) -> InvitationResponse:
    return InvitationResponse(
        id=record.public_id,
        organization_id=organization_id,
        email=record.email,
        role=record.role,
        status=record.status,
        version=record.version,
        invited_by=record.invited_by,
        expires_at=record.expires_at,
        accepted_at=record.accepted_at,
    )


@router.get("/api/organizations/current", response_model=OrganizationDetailResponse)
def get_current_organization(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> OrganizationDetailResponse:
    _authorize(actor, Permission.ORGANIZATION_READ)
    try:
        with _database(request).session() as session:
            record = OrganizationService(OrganizationRepository(session)).get_current(actor)
    except (PermissionDenied, OrganizationNotFound) as exc:
        raise _translate(exc) from exc
    return OrganizationDetailResponse(data=_organization_response(record))


@router.get("/api/members", response_model=MemberListResponse)
def list_members(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> MemberListResponse:
    _authorize(actor, Permission.MEMBER_READ)
    try:
        with _database(request).session() as session:
            records = OrganizationService(OrganizationRepository(session)).list_members(actor)
    except (PermissionDenied, OrganizationNotFound) as exc:
        raise _translate(exc) from exc
    items = [_member_response(record, actor.organization_id) for record in records]
    return MemberListResponse(items=items, next_cursor=None, total=len(items))


@router.get("/api/invitations", response_model=InvitationListResponse)
def list_invitations(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InvitationListResponse:
    _authorize(actor, Permission.MEMBER_INVITE)
    try:
        with _database(request).session() as session:
            records = OrganizationService(OrganizationRepository(session)).list_invitations(actor)
    except (PermissionDenied, OrganizationNotFound) as exc:
        raise _translate(exc) from exc
    items = [_invitation_response(record, actor.organization_id) for record in records]
    return InvitationListResponse(items=items, next_cursor=None, total=len(items))


@router.post("/api/invitations", response_model=InvitationDetailResponse, status_code=201)
def create_invitation(
    command: CreateInvitationRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InvitationDetailResponse:
    _authorize(actor, Permission.MEMBER_INVITE)
    correlation_id = str(request.state.correlation_id)
    gateway: ClerkIdentityGateway | None = request.app.state.invitation_gateway
    provider_invitation_id: str | None = None
    try:
        with _database(request).session() as session:
            repository = OrganizationRepository(session)
            record = OrganizationService(repository).invite_member(
                actor=actor,
                email=command.email,
                role=command.role,
                correlation_id=correlation_id,
            )
            if gateway is not None:
                provider_invitation_id = gateway.create_invitation(
                    email=str(record.email),
                    invitation_id=record.public_id,
                    organization_id=actor.organization_id,
                    role=record.role.value,
                )
                record = repository.attach_invitation_delivery(
                    organization_public_id=actor.organization_id,
                    invitation_public_id=record.public_id,
                    provider_invitation_id=provider_invitation_id,
                )
    except (
        PermissionDenied,
        OrganizationNotFound,
        ActorMembershipNotFound,
        InvitationConflict,
        InvitationDeliveryUnavailable,
    ) as exc:
        raise _translate(exc) from exc
    except Exception:
        if gateway is not None and provider_invitation_id is not None:
            try:
                gateway.revoke_invitation(provider_invitation_id)
            except InvitationDeliveryUnavailable:
                logger.error(
                    "invitation_creation_compensation_failed",
                    extra={"correlation_id": correlation_id},
                )
        raise
    return InvitationDetailResponse(data=_invitation_response(record, actor.organization_id))


@router.patch("/api/members/{member_id}", response_model=MemberDetailResponse)
def update_member(
    member_id: str,
    command: UpdateMemberRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> MemberDetailResponse:
    _authorize(actor, Permission.MEMBER_MANAGE)
    try:
        with _database(request).session() as session:
            record = OrganizationService(OrganizationRepository(session)).update_member(
                actor=actor,
                member_id=member_id,
                expected_version=command.expected_version,
                role=command.role,
                status=MemberStatus(command.status) if command.status is not None else None,
                correlation_id=str(request.state.correlation_id),
            )
    except (
        PermissionDenied,
        OrganizationNotFound,
        ActorMembershipNotFound,
        MemberNotFound,
        MemberConflict,
        MemberVersionConflict,
    ) as exc:
        raise _translate(exc) from exc
    return MemberDetailResponse(
        data=_member_response(record, actor.organization_id)
    )


@router.post(
    "/api/invitations/{invitation_id}/revoke",
    response_model=InvitationDetailResponse,
)
def revoke_invitation(
    invitation_id: str,
    command: RevokeInvitationRequest,
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
) -> InvitationDetailResponse:
    _authorize(actor, Permission.MEMBER_MANAGE)
    gateway: ClerkIdentityGateway | None = request.app.state.invitation_gateway
    try:
        with _database(request).session() as session:
            record = OrganizationService(
                OrganizationRepository(session)
            ).revoke_invitation(
                actor=actor,
                invitation_id=invitation_id,
                expected_version=command.expected_version,
                correlation_id=str(request.state.correlation_id),
            )
    except (
        PermissionDenied,
        OrganizationNotFound,
        ActorMembershipNotFound,
        InvitationNotFound,
        InvitationConflict,
        InvitationVersionConflict,
    ) as exc:
        raise _translate(exc) from exc
    if gateway is not None and record.provider_invitation_id is not None:
        try:
            gateway.revoke_invitation(record.provider_invitation_id)
        except InvitationDeliveryUnavailable as exc:
            raise AppError(
                code="invitation_provider_revoke_failed",
                message=(
                    "Workspace access was revoked, but the sign-in invitation "
                    "could not be withdrawn."
                ),
                status_code=503,
            ) from exc
    return InvitationDetailResponse(
        data=_invitation_response(record, actor.organization_id)
    )
