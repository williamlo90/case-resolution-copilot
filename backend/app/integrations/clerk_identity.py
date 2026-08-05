from collections.abc import Mapping
from urllib.parse import quote

import httpx

from app.domain.identity import InvitedIdentity


class InvitationDeliveryUnavailable(RuntimeError):
    pass


class IdentityDirectoryUnavailable(RuntimeError):
    pass


class InvitedIdentityNotFound(LookupError):
    pass


class ClerkAPIError(RuntimeError):
    pass


class ClerkIdentityGateway:
    def __init__(
        self,
        *,
        secret_key: str,
        invitation_redirect_url: str,
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._client = client or httpx.Client(
            base_url="https://api.clerk.com/v1",
            timeout=timeout_seconds,
        )
        self._owns_client = client is None
        self._headers = {
            "Authorization": f"Bearer {secret_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._invitation_redirect_url = invitation_redirect_url

    def create_invitation(
        self,
        *,
        email: str,
        invitation_id: str,
        organization_id: str,
        role: str,
    ) -> str:
        try:
            invitation = self._request_json(
                "POST",
                "/invitations",
                payload={
                    "email_address": email,
                    "redirect_url": self._invitation_redirect_url,
                    "public_metadata": {
                        "support_copilot_invitation_id": invitation_id,
                        "support_copilot_organization_id": organization_id,
                        "support_copilot_role": role,
                    },
                    "notify": True,
                    "ignore_existing": True,
                    "expires_in_days": 7,
                },
            )
        except ClerkAPIError:
            raise InvitationDeliveryUnavailable("The invitation email could not be sent.") from None
        provider_id = invitation.get("id")
        if not isinstance(provider_id, str) or not provider_id:
            raise InvitationDeliveryUnavailable(
                "The identity provider returned no invitation reference."
            )
        return provider_id

    def revoke_invitation(self, provider_invitation_id: str) -> None:
        invitation_id = quote(provider_invitation_id, safe="")
        try:
            self._request_json("POST", f"/invitations/{invitation_id}/revoke")
        except ClerkAPIError:
            raise InvitationDeliveryUnavailable(
                "The sign-in invitation could not be revoked."
            ) from None

    def get_invited_identity(self, subject_id: str) -> InvitedIdentity:
        user_id = quote(subject_id, safe="")
        try:
            user = self._request_json("GET", f"/users/{user_id}")
        except ClerkAPIError:
            raise IdentityDirectoryUnavailable(
                "The identity provider could not load the account."
            ) from None

        primary_email_id = user.get("primary_email_address_id")
        primary_email = _primary_email(user, primary_email_id)
        verification = _mapping(primary_email.get("verification"))
        status = verification.get("status")
        email = primary_email.get("email_address")
        if status != "verified" or not isinstance(email, str) or not email:
            raise InvitedIdentityNotFound("The account has no verified primary email address.")

        metadata = _mapping(user.get("public_metadata"))
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        name = " ".join(part for part in (first_name, last_name) if isinstance(part, str) and part)
        if not name:
            name = email.split("@", 1)[0]

        return InvitedIdentity(
            subject_id=subject_id,
            email=email.lower(),
            name=name,
            invitation_id=_metadata_string(
                metadata,
                "support_copilot_invitation_id",
            ),
            organization_id=_metadata_string(
                metadata,
                "support_copilot_organization_id",
            ),
            role=_metadata_string(metadata, "support_copilot_role"),
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        try:
            response = self._client.request(
                method,
                path,
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()
            body: object = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ClerkAPIError from error
        if not isinstance(body, dict):
            raise ClerkAPIError("The identity provider returned an invalid response.")
        return {key: value for key, value in body.items() if isinstance(key, str)}


def _primary_email(
    user: Mapping[str, object],
    primary_email_id: object,
) -> Mapping[str, object]:
    raw_addresses = user.get("email_addresses")
    addresses = raw_addresses if isinstance(raw_addresses, list) else []
    return next(
        (
            address
            for raw_address in addresses
            if (address := _mapping(raw_address)).get("id") == primary_email_id
        ),
        {},
    )


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, str)}


def _metadata_string(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None
