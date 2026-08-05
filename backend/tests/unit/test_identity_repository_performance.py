from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.persistence.identity_repository import OrganizationRepository
from app.persistence.models import MembershipModel, OrganizationModel


def test_actor_resolution_joins_membership_and_organization_once() -> None:
    organization_id = uuid4()
    organization = OrganizationModel(
        id=organization_id,
        public_id="ORG-0001",
        name="Northstar Cloud",
        slug="northstar-cloud",
        version=3,
    )
    member = MembershipModel(
        id=uuid4(),
        public_id="USR-0003",
        organization_id=organization_id,
        subject_id="user_clerk",
        name="Ari Administrator",
        email="ari@example.com",
        role="administrator",
        status="active",
        version=1,
    )
    result = MagicMock()
    result.all.return_value = [
        (
            member,
            organization,
            {
                "organization_name": "Northstar Cloud",
                "locale": "en-GB",
                "time_zone": "Europe/London",
            },
        )
    ]
    session = MagicMock(spec=Session)
    session.execute.return_value = result

    actor = OrganizationRepository(session).resolve_actor_by_subject(
        "user_clerk",
    )

    assert actor.organization is not None
    assert actor.organization.id == "ORG-0001"
    assert actor.organization.name == "Northstar Cloud"
    assert actor.organization.version == 3
    assert actor.organization.locale == "en-GB"
    assert actor.organization.time_zone == "Europe/London"
    session.execute.assert_called_once()
    session.scalars.assert_not_called()
    session.get.assert_not_called()


def test_actor_resolution_uses_safe_presentation_defaults() -> None:
    organization_id = uuid4()
    organization = OrganizationModel(
        id=organization_id,
        public_id="ORG-0001",
        name="Northstar Cloud",
        slug="northstar-cloud",
        version=3,
    )
    member = MembershipModel(
        id=uuid4(),
        public_id="USR-0003",
        organization_id=organization_id,
        subject_id="user_clerk",
        name="Ari Administrator",
        email="ari@example.com",
        role="administrator",
        status="active",
        version=1,
    )
    result = MagicMock()
    result.all.return_value = [(member, organization, None)]
    session = MagicMock(spec=Session)
    session.execute.return_value = result

    actor = OrganizationRepository(session).resolve_actor_by_subject("user_clerk")

    assert actor.organization is not None
    assert actor.organization.locale == "en-US"
    assert actor.organization.time_zone == "Asia/Jakarta"
