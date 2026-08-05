import json
from collections.abc import Callable

import httpx
import pytest

from app.integrations.clerk_identity import (
    ClerkIdentityGateway,
    InvitationDeliveryUnavailable,
    InvitedIdentityNotFound,
)


def _user(*, verified: bool = True) -> dict[str, object]:
    return {
        "primary_email_address_id": "email_123",
        "email_addresses": [
            {
                "id": "email_123",
                "email_address": "New.Member@Example.com",
                "verification": {
                    "status": "verified" if verified else "unverified",
                },
            }
        ],
        "first_name": "New",
        "last_name": "Member",
        "public_metadata": {
            "support_copilot_invitation_id": "INV-TEST",
            "support_copilot_organization_id": "ORG-0001",
            "support_copilot_role": "specialist",
        },
    }


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(
        base_url="https://api.clerk.com/v1",
        transport=httpx.MockTransport(handler),
    )


def test_gateway_sends_and_revokes_a_bound_invitation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/invitations":
            return httpx.Response(200, json={"id": "inv_clerk_123"})
        return httpx.Response(200, json={"id": "inv_clerk_123", "status": "revoked"})

    with _client(handler) as client:
        gateway = ClerkIdentityGateway(
            secret_key="test-secret",
            client=client,
            invitation_redirect_url="https://app.example.com/invite",
        )

        provider_id = gateway.create_invitation(
            email="new.member@example.com",
            invitation_id="INV-TEST",
            organization_id="ORG-0001",
            role="specialist",
        )
        gateway.revoke_invitation(provider_id)

    assert provider_id == "inv_clerk_123"
    assert [request.url.path for request in requests] == [
        "/v1/invitations",
        "/v1/invitations/inv_clerk_123/revoke",
    ]
    assert requests[0].headers["Authorization"] == "Bearer test-secret"
    payload = json.loads(requests[0].content)
    assert payload == {
        "email_address": "new.member@example.com",
        "redirect_url": "https://app.example.com/invite",
        "public_metadata": {
            "support_copilot_invitation_id": "INV-TEST",
            "support_copilot_organization_id": "ORG-0001",
            "support_copilot_role": "specialist",
        },
        "notify": True,
        "ignore_existing": True,
        "expires_in_days": 7,
    }


def test_gateway_returns_only_verified_invitation_identity() -> None:
    with _client(lambda _: httpx.Response(200, json=_user())) as client:
        gateway = ClerkIdentityGateway(
            secret_key="test-secret",
            client=client,
            invitation_redirect_url="https://app.example.com/invite",
        )

        identity = gateway.get_invited_identity("user_123")

    assert str(identity.email) == "new.member@example.com"
    assert identity.name == "New Member"
    assert identity.invitation_id == "INV-TEST"
    assert identity.organization_id == "ORG-0001"
    assert identity.role == "specialist"


def test_gateway_fails_closed_without_verified_email_or_delivery() -> None:
    with _client(lambda _: httpx.Response(200, json=_user(verified=False))) as client:
        unverified_gateway = ClerkIdentityGateway(
            secret_key="test-secret",
            client=client,
            invitation_redirect_url="https://app.example.com/invite",
        )
        with pytest.raises(InvitedIdentityNotFound):
            unverified_gateway.get_invited_identity("user_123")

    with _client(lambda _: httpx.Response(503, json={"error": "unavailable"})) as client:
        failing_gateway = ClerkIdentityGateway(
            secret_key="test-secret",
            client=client,
            invitation_redirect_url="https://app.example.com/invite",
        )
        with pytest.raises(InvitationDeliveryUnavailable, match="could not be sent"):
            failing_gateway.create_invitation(
                email="new.member@example.com",
                invitation_id="INV-TEST",
                organization_id="ORG-0001",
                role="specialist",
            )
