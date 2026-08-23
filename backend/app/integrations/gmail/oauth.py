from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from pydantic import SecretStr

from app.domain.inbox import (
    AccessCredential,
    AuthorizationCallback,
    AuthorizationRequest,
    GrantedCredential,
    InboxAuthorizationError,
    RefreshCredential,
    RevocationResult,
)

from .transport import GmailTransport

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOCATION_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_DRAFT_SCOPE = "https://www.googleapis.com/auth/gmail.compose"


class GmailAuthorizationAdapter:
    provider_name = "gmail"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        timeout_seconds: float,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = GmailTransport(timeout_seconds=timeout_seconds)

    def authorization_url(self, request: AuthorizationRequest) -> str:
        if request.client_id != self._client_id:
            raise InboxAuthorizationError("The OAuth client does not match this adapter.")
        return GOOGLE_AUTHORIZATION_URL + "?" + urlencode(
            {
                "access_type": "offline",
                "client_id": request.client_id,
                "code_challenge": request.code_challenge,
                "code_challenge_method": "S256",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "redirect_uri": request.redirect_uri,
                "response_type": "code",
                "scope": " ".join(request.scopes),
                "state": request.state,
                **({"login_hint": request.login_hint} if request.login_hint else {}),
            }
        )

    def exchange_code(self, callback: AuthorizationCallback) -> GrantedCredential:
        payload = self._transport.request_json(
            "POST",
            GOOGLE_TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": callback.code.get_secret_value(),
                "code_verifier": callback.code_verifier.get_secret_value(),
                "grant_type": "authorization_code",
                "redirect_uri": callback.redirect_uri,
            },
            authorization_request=True,
        )
        refresh_token = _required_string(payload, "refresh_token")
        return GrantedCredential(
            access_token=SecretStr(_required_string(payload, "access_token")),
            refresh_token=SecretStr(refresh_token),
            granted_scopes=tuple(_required_string(payload, "scope").split()),
            expires_at=_expiry(payload),
        )

    def refresh_access(self, credential: RefreshCredential) -> AccessCredential:
        payload = self._transport.request_json(
            "POST",
            GOOGLE_TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
                "refresh_token": credential.refresh_token.get_secret_value(),
            },
            authorization_request=True,
        )
        return AccessCredential(
            access_token=SecretStr(_required_string(payload, "access_token")),
            expires_at=_expiry(payload),
        )

    def revoke(self, credential: RefreshCredential) -> RevocationResult:
        self._transport.request_ok(
            "POST",
            GOOGLE_REVOCATION_URL,
            data={"token": credential.refresh_token.get_secret_value()},
            authorization_request=True,
        )
        return RevocationResult(revoked=True, provider_confirmed=True)

    def close(self) -> None:
        self._transport.close()


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise InboxAuthorizationError("Inbox authorization returned incomplete credentials.")
    return value


def _expiry(payload: dict[str, object]) -> datetime:
    value = payload.get("expires_in")
    if not isinstance(value, int) or value <= 0:
        raise InboxAuthorizationError("Inbox authorization returned an invalid expiry.")
    return datetime.now(UTC) + timedelta(seconds=value)
