from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import EmailStr

from app.domain.identity import (
    InvitationRecord,
    InvitationStatus,
    MemberRecord,
    MemberRole,
    MemberStatus,
    OrganizationNotFound,
    OrganizationRecord,
)
from app.security.authentication import DeterministicAuthProvider
from app.security.authorization import PermissionDenied
from app.services.organization_service import OrganizationService


class FakeOrganizationStore:
    def __init__(self, organization: OrganizationRecord | None) -> None:
        self.organization = organization
        self.organization_lookups: list[str] = []
        self.invitation_organization_id: str | None = None
        self.member_update_organization_id: str | None = None

    def get_organization(self, organization_public_id: str) -> OrganizationRecord | None:
        self.organization_lookups.append(organization_public_id)
        if self.organization and self.organization.public_id == organization_public_id:
            return self.organization
        return None

    def list_members(self, organization_public_id: str) -> list[MemberRecord]:
        self.organization_lookups.append(organization_public_id)
        return []

    def list_invitations(self, organization_public_id: str) -> list[InvitationRecord]:
        self.organization_lookups.append(organization_public_id)
        return []

    def create_invitation(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        email: EmailStr,
        role: MemberRole,
        correlation_id: str,
    ) -> InvitationRecord:
        del correlation_id
        self.invitation_organization_id = organization_public_id
        return InvitationRecord(
            id=uuid4(),
            public_id="INV-TEST",
            organization_id=uuid4(),
            email=email,
            role=role,
            status=InvitationStatus.PENDING,
            version=1,
            invited_by=actor_id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            accepted_at=None,
        )

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
    ) -> MemberRecord:
        del actor_id, expected_version, correlation_id
        self.member_update_organization_id = organization_public_id
        return MemberRecord(
            id=uuid4(),
            public_id=member_public_id,
            organization_id=uuid4(),
            subject_id=member_public_id,
            name="Updated Member",
            email="updated.member@example.com",
            role=role or MemberRole.SPECIALIST,
            status=status or MemberStatus.ACTIVE,
            version=2,
            last_active_at=None,
        )

    def revoke_invitation(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        invitation_public_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> InvitationRecord:
        del (
            organization_public_id,
            actor_id,
            invitation_public_id,
            expected_version,
            correlation_id,
        )
        raise AssertionError("Invitation revocation is not used in this test.")


def _organization(public_id: str = "ORG-0001") -> OrganizationRecord:
    now = datetime.now(UTC)
    return OrganizationRecord(
        id=uuid4(),
        public_id=public_id,
        name="Northstar Cloud",
        slug="northstar-cloud",
        version=1,
        created_at=now,
        updated_at=now,
    )


def test_service_uses_actor_organization_as_the_only_tenant_scope() -> None:
    store = FakeOrganizationStore(_organization())
    actor = DeterministicAuthProvider().authenticate("USR-0002")

    OrganizationService(store).list_members(actor)

    assert store.organization_lookups == ["ORG-0001", "ORG-0001"]


def test_service_cannot_fall_through_to_another_organization() -> None:
    store = FakeOrganizationStore(_organization("ORG-OTHER"))
    actor = DeterministicAuthProvider().authenticate("USR-0002")

    with pytest.raises(OrganizationNotFound):
        OrganizationService(store).get_current(actor)

    assert store.organization_lookups == ["ORG-0001"]


def test_specialist_cannot_invite_by_supplying_a_different_role() -> None:
    store = FakeOrganizationStore(_organization())
    specialist = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(PermissionDenied):
        OrganizationService(store).invite_member(
            actor=specialist,
            email="new.member@example.com",
            role=MemberRole.ADMINISTRATOR,
            correlation_id="corr_test",
        )

    assert store.invitation_organization_id is None


def test_administrator_invitation_remains_actor_scoped() -> None:
    store = FakeOrganizationStore(_organization())
    administrator = DeterministicAuthProvider().authenticate("USR-0003")

    invitation = OrganizationService(store).invite_member(
        actor=administrator,
        email="new.member@example.com",
        role=MemberRole.SPECIALIST,
        correlation_id="corr_test",
    )

    assert invitation.invited_by == "USR-0003"
    assert store.invitation_organization_id == "ORG-0001"


def test_only_administrator_can_change_member_authority() -> None:
    store = FakeOrganizationStore(_organization())
    supervisor = DeterministicAuthProvider().authenticate("USR-0002")
    administrator = DeterministicAuthProvider().authenticate("USR-0003")

    with pytest.raises(PermissionDenied):
        OrganizationService(store).update_member(
            actor=supervisor,
            member_id="USR-0001",
            expected_version=1,
            role=MemberRole.SUPERVISOR,
            status=None,
            correlation_id="corr_test",
        )

    updated = OrganizationService(store).update_member(
        actor=administrator,
        member_id="USR-0001",
        expected_version=1,
        role=MemberRole.SUPERVISOR,
        status=None,
        correlation_id="corr_test",
    )

    assert updated.role is MemberRole.SUPERVISOR
    assert store.member_update_organization_id == "ORG-0001"
