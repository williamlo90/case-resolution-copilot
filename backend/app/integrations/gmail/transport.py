import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.domain.inbox import (
    InboxAuthorizationError,
    InboxProviderUnavailable,
)

_GOOGLE_OAUTH_ENDPOINTS = {
    ("POST", "oauth2.googleapis.com", "/token"),
    ("POST", "oauth2.googleapis.com", "/revoke"),
}
_GMAIL_ENDPOINTS = (
    ("GET", re.compile(r"^/gmail/v1/users/me/(?:profile|threads|history|drafts)$")),
    (
        "GET",
        re.compile(
            r"^/gmail/v1/users/me/(?:threads|messages|drafts)/[A-Za-z0-9_-]+$"
        ),
    ),
    ("POST", re.compile(r"^/gmail/v1/users/me/drafts$")),
)


class GmailTransport:
    def __init__(self, *, timeout_seconds: float) -> None:
        self._client = httpx.Client(timeout=timeout_seconds)

    def request_json(
        self,
        method: str,
        url: str,
        *,
        access_token: str | None = None,
        params: dict[str, str | int | list[str]] | None = None,
        data: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        authorization_request: bool = False,
    ) -> dict[str, Any]:
        _require_allowed_endpoint(
            method,
            url,
            access_token=access_token,
            authorization_request=authorization_request,
        )
        headers = (
            {"Authorization": f"Bearer {access_token}"}
            if access_token is not None
            else None
        )
        try:
            response = self._client.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                json=json,
            )
        except httpx.TimeoutException as exc:
            raise InboxProviderUnavailable("The inbox provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise InboxProviderUnavailable("The inbox provider is unavailable.") from exc
        if response.status_code >= 400:
            if authorization_request and response.status_code in {400, 401, 403}:
                raise InboxAuthorizationError("Inbox authorization was rejected.")
            if response.status_code in {401, 403}:
                raise InboxAuthorizationError("Inbox authorization is no longer valid.")
            raise InboxProviderUnavailable(
                f"The inbox provider returned status {response.status_code}."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise InboxProviderUnavailable(
                "The inbox provider returned an invalid response."
            ) from exc
        if not isinstance(payload, dict):
            raise InboxProviderUnavailable("The inbox provider returned an invalid response.")
        return payload

    def request_ok(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str],
        authorization_request: bool = False,
    ) -> None:
        _require_allowed_endpoint(
            method,
            url,
            access_token=None,
            authorization_request=authorization_request,
        )
        try:
            response = self._client.request(method, url, data=data)
        except httpx.TimeoutException as exc:
            raise InboxProviderUnavailable("The inbox provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise InboxProviderUnavailable("The inbox provider is unavailable.") from exc
        if response.status_code >= 400:
            if authorization_request and response.status_code in {400, 401, 403}:
                raise InboxAuthorizationError("Inbox authorization was rejected.")
            raise InboxProviderUnavailable(
                f"The inbox provider returned status {response.status_code}."
            )

    def close(self) -> None:
        self._client.close()


def _require_allowed_endpoint(
    method: str,
    url: str,
    *,
    access_token: str | None,
    authorization_request: bool,
) -> None:
    parsed = urlsplit(url)
    normalized_method = method.upper()
    invalid_origin = (
        parsed.scheme != "https"
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.query)
        or bool(parsed.fragment)
    )
    if invalid_origin:
        raise InboxProviderUnavailable("The inbox provider endpoint is not allowed.")
    host = (parsed.hostname or "").casefold()
    oauth_allowed = (
        authorization_request
        and access_token is None
        and (normalized_method, host, parsed.path) in _GOOGLE_OAUTH_ENDPOINTS
    )
    gmail_allowed = (
        not authorization_request
        and access_token is not None
        and host == "gmail.googleapis.com"
        and any(
            normalized_method == allowed_method and pattern.fullmatch(parsed.path)
            for allowed_method, pattern in _GMAIL_ENDPOINTS
        )
    )
    if not oauth_allowed and not gmail_allowed:
        raise InboxProviderUnavailable("The inbox provider endpoint is not allowed.")
