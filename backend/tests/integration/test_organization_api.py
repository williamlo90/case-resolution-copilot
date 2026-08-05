from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.domain.identity import InvitedIdentity, MemberRole
from app.main import create_app
from app.persistence.database import Database
from app.persistence.identity_repository import OrganizationRepository
from app.persistence.models import (
    AuditEventModel,
    InvitationModel,
    MembershipModel,
    OrganizationModel,
)

ADMIN = {"X-Actor-ID": "USR-0003"}


def _seed_organizations(database: Database) -> None:
    with database.session() as session:
        primary = OrganizationModel(
            public_id="ORG-0001", name="Northstar Cloud", slug="northstar-cloud"
        )
        other = OrganizationModel(
            public_id="ORG-0002", name="Other Organization", slug="other-organization"
        )
        session.add_all([primary, other])
        session.flush()
        session.add_all(
            [
                MembershipModel(
                    public_id="USR-0001",
                    organization_id=primary.id,
                    subject_id="USR-0001",
                    name="Maya Specialist",
                    email="maya.specialist@example.com",
                    role="specialist",
                    status="active",
                ),
                MembershipModel(
                    public_id="USR-0003",
                    organization_id=primary.id,
                    subject_id="USR-0003",
                    name="Ari Administrator",
                    email="ari.administrator@example.com",
                    role="administrator",
                    status="active",
                ),
                MembershipModel(
                    public_id="USR-9001",
                    organization_id=other.id,
                    subject_id="USR-9001",
                    name="Other Member",
                    email="other.member@example.com",
                    role="administrator",
                    status="active",
                ),
            ]
        )


def test_organization_reads_and_invites_remain_tenant_scoped(
    database: Database, test_database_url: str
) -> None:
    _seed_organizations(database)
    app = create_app(Settings(environment="test", database_url=test_database_url, _env_file=None))

    with TestClient(app) as client:
        organization = client.get("/api/organizations/current", headers=ADMIN)
        members = client.get(
            "/api/members",
            headers={**ADMIN, "X-Organization-ID": "ORG-0002"},
        )
        spoofed = client.post(
            "/api/invitations",
            headers={"X-Actor-ID": "USR-0001", "X-Actor-Role": "administrator"},
            json={"email": "new.member@example.com", "role": "specialist"},
        )
        existing_member = client.post(
            "/api/invitations",
            headers=ADMIN,
            json={
                "email": "maya.specialist@example.com",
                "role": "specialist",
            },
        )
        created = client.post(
            "/api/invitations",
            headers=ADMIN,
            json={"email": "new.member@example.com", "role": "specialist"},
        )
        duplicate = client.post(
            "/api/invitations",
            headers=ADMIN,
            json={"email": "new.member@example.com", "role": "specialist"},
        )

    assert organization.status_code == 200
    assert organization.json()["data"]["id"] == "ORG-0001"
    assert members.status_code == 200
    assert {item["id"] for item in members.json()["items"]} == {"USR-0001", "USR-0003"}
    assert spoofed.status_code == 403
    assert existing_member.status_code == 409
    assert created.status_code == 201
    assert created.json()["data"]["organization_id"] == "ORG-0001"
    assert duplicate.status_code == 409

    with database.session() as session:
        claimed_actor = OrganizationRepository(session).accept_invitation(
            identity=InvitedIdentity(
                subject_id="user_clerk_new",
                email="new.member@example.com",
                name="New Member",
                invitation_id="INV-STALE",
                organization_id="ORG-STALE",
                role="supervisor",
            ),
            correlation_id="corr_accept",
        )
        repeated_actor = OrganizationRepository(session).accept_invitation(
            identity=InvitedIdentity(
                subject_id="user_clerk_new",
                email="new.member@example.com",
                name="New Member",
                invitation_id=created.json()["data"]["id"],
                organization_id="ORG-0001",
                role="specialist",
            ),
            correlation_id="corr_accept_repeated",
        )

    assert claimed_actor.role is MemberRole.SPECIALIST
    assert claimed_actor.organization_id == "ORG-0001"
    assert repeated_actor.actor_id == claimed_actor.actor_id

    with database.session() as session:
        event = session.scalar(
            select(AuditEventModel).where(AuditEventModel.event_type == "membership.invited")
        )
        organization_id = session.scalar(
            select(OrganizationModel.id).where(OrganizationModel.public_id == "ORG-0001")
        )
        assert event is not None
        assert event.organization_id == organization_id
        assert event.task_id is None
        assert event.data == {"role": "specialist"}
        accepted = session.scalar(
            select(AuditEventModel).where(
                AuditEventModel.event_type == "membership.invitation_accepted"
            )
        )
        assert accepted is not None
        assert accepted.data["member_id"] == claimed_actor.actor_id


def test_database_rejects_an_inviter_from_another_organization(
    database: Database,
) -> None:
    _seed_organizations(database)

    with pytest.raises(IntegrityError), database.session() as session:
        primary_id = session.scalar(
            select(OrganizationModel.id).where(OrganizationModel.public_id == "ORG-0001")
        )
        other_member_id = session.scalar(
            select(MembershipModel.id).where(MembershipModel.public_id == "USR-9001")
        )
        assert primary_id is not None
        assert other_member_id is not None
        session.add(
            InvitationModel(
                public_id="INV-CROSS-TENANT",
                organization_id=primary_id,
                email="cross.tenant@example.com",
                role="specialist",
                status="pending",
                invited_by_id=other_member_id,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        session.flush()
