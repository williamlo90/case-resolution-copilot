from typing import Protocol

from pydantic import EmailStr

from app.domain.identity import (
    ActorContext,
    InvitationRecord,
    MemberRecord,
    MemberRole,
    MemberStatus,
    OrganizationNotFound,
    OrganizationRecord,
    Permission,
)
from app.security.authorization import require_permission


class OrganizationStore(Protocol):
    def get_organization(self, organization_public_id: str) -> OrganizationRecord | None: ...

    def list_members(self, organization_public_id: str) -> list[MemberRecord]: ...

    def list_invitations(self, organization_public_id: str) -> list[InvitationRecord]: ...

    def create_invitation(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        email: EmailStr,
        role: MemberRole,
        correlation_id: str,
    ) -> InvitationRecord: ...

    def update_member(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        member_public_id: str,
        expected_version: int,
        role: MemberRole | None,
        status: MemberStatus | None,
        correlation_id: str,
    ) -> MemberRecord: ...

    def revoke_invitation(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        invitation_public_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> InvitationRecord: ...


class OrganizationService:
    def __init__(self, store: OrganizationStore) -> None:
        self._store = store

    def get_current(self, actor: ActorContext) -> OrganizationRecord:
        require_permission(actor, Permission.ORGANIZATION_READ)
        organization = self._store.get_organization(actor.organization_id)
        if organization is None:
            raise OrganizationNotFound("The actor organization was not found.")
        return organization

    def list_members(self, actor: ActorContext) -> list[MemberRecord]:
        require_permission(actor, Permission.MEMBER_READ)
        self.get_current(actor)
        return self._store.list_members(actor.organization_id)

    def list_invitations(self, actor: ActorContext) -> list[InvitationRecord]:
        require_permission(actor, Permission.MEMBER_INVITE)
        self.get_current(actor)
        return self._store.list_invitations(actor.organization_id)

    def invite_member(
        self,
        *,
        actor: ActorContext,
        email: EmailStr,
        role: MemberRole,
        correlation_id: str,
    ) -> InvitationRecord:
        require_permission(actor, Permission.MEMBER_INVITE)
        self.get_current(actor)
        return self._store.create_invitation(
            organization_public_id=actor.organization_id,
            actor_id=actor.actor_id,
            email=email,
            role=role,
            correlation_id=correlation_id,
        )

    def update_member(
        self,
        *,
        actor: ActorContext,
        member_id: str,
        expected_version: int,
        role: MemberRole | None,
        status: MemberStatus | None,
        correlation_id: str,
    ) -> MemberRecord:
        require_permission(actor, Permission.MEMBER_MANAGE)
        self.get_current(actor)
        return self._store.update_member(
            organization_public_id=actor.organization_id,
            actor_id=actor.actor_id,
            member_public_id=member_id,
            expected_version=expected_version,
            role=role,
            status=status,
            correlation_id=correlation_id,
        )

    def revoke_invitation(
        self,
        *,
        actor: ActorContext,
        invitation_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> InvitationRecord:
        require_permission(actor, Permission.MEMBER_MANAGE)
        self.get_current(actor)
        return self._store.revoke_invitation(
            organization_public_id=actor.organization_id,
            actor_id=actor.actor_id,
            invitation_public_id=invitation_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
        )
