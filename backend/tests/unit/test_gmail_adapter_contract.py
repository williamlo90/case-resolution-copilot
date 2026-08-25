from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from hashlib import sha256
from inspect import getsource

import httpx
import pytest

from app.domain.inbox import (
    AccessCredential,
    AuthorizationRequest,
    InboxAuthorizationError,
    InboxProviderUnavailable,
)
from app.integrations.gmail import (
    GmailAuthorizationAdapter,
    GmailDraftAdapter,
    GmailReadAdapter,
)
from app.integrations.gmail.normalization import normalize_message
from app.integrations.gmail.oauth import GMAIL_DRAFT_SCOPE, GMAIL_READ_SCOPE
from app.integrations.gmail.transport import GmailTransport


def _encoded(value: str) -> str:
    return urlsafe_b64encode(value.encode()).decode().rstrip("=")


def test_gmail_normalizer_prefers_plain_text_and_keeps_attachments_metadata_only() -> None:
    payload = {
        "id": "message-1",
        "threadId": "thread-1",
        "internalDate": "1786496400000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "Customer <customer@example.com>"},
                {"name": "To", "value": "support@example.com"},
                {"name": "Subject", "value": "Invoice question"},
                {"name": "Message-ID", "value": "<message-1@example.com>"},
            ],
            "parts": [
                {"mimeType": "text/html", "body": {"data": _encoded("<b>HTML</b>")}},
                {"mimeType": "text/plain", "body": {"data": _encoded("Plain answer")}},
                {
                    "mimeType": "application/pdf",
                    "filename": "invoice.pdf",
                    "body": {"attachmentId": "attachment-1", "size": 512},
                },
            ],
        },
    }

    message = normalize_message(payload, account_address="support@example.com")

    assert message.body == "Plain answer"
    assert message.direction == "inbound"
    assert message.rfc_message_id == "<message-1@example.com>"
    assert len(message.attachments) == 1
    assert message.attachments[0].content_status == "metadata_only"
    assert message.attachments[0].reported_size == 512


def test_gmail_authorization_uses_pkce_and_incremental_offline_consent() -> None:
    adapter = GmailAuthorizationAdapter(
        client_id="client-id",
        client_secret="client-secret",
        timeout_seconds=1,
    )
    try:
        url = adapter.authorization_url(
            AuthorizationRequest(
                client_id="client-id",
                redirect_uri="https://app.example.com/connections/inbox/callback",
                scopes=(GMAIL_READ_SCOPE, GMAIL_DRAFT_SCOPE),
                state="s" * 48,
                code_challenge="c" * 43,
                login_hint="admin@example.com",
            )
        )
    finally:
        adapter.close()

    assert "access_type=offline" in url
    assert "include_granted_scopes=true" in url
    assert "code_challenge_method=S256" in url
    assert "prompt=consent" in url


def test_gmail_thread_listing_uses_one_metadata_lookup_per_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = GmailReadAdapter(timeout_seconds=1)
    calls: list[tuple[str, dict[str, object] | None]] = []
    timestamp = str(int(datetime(2026, 8, 12, tzinfo=UTC).timestamp() * 1000))

    def fake_get(
        path: str,
        *,
        access: AccessCredential,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        del access
        calls.append((path, params))
        if path == "/threads":
            return {
                "threads": [{"id": "thread-1"}, {"id": "thread-2"}],
                "nextPageToken": "next-page",
                "historyId": "history-2",
            }
        thread_id = path.removeprefix("/threads/")
        return {
            "messages": [
                {
                    "id": f"message-{thread_id}",
                    "threadId": thread_id,
                    "internalDate": timestamp,
                    "payload": {
                        "headers": [
                            {"name": "Subject", "value": f"Subject {thread_id}"}
                        ]
                    },
                }
            ]
        }

    monkeypatch.setattr(adapter, "_get", fake_get)
    try:
        page = adapter.list_threads(
            access=AccessCredential(
                access_token="access-token",
                expires_at=datetime(2026, 8, 13, tzinfo=UTC),
            ),
            label_filter=("INBOX",),
            after=datetime(2026, 8, 1, tzinfo=UTC),
            page_token=None,
            limit=2,
        )
    finally:
        adapter.close()

    assert [item.subject for item in page.items] == [
        "Subject thread-1",
        "Subject thread-2",
    ]
    assert [path for path, _params in calls] == [
        "/threads",
        "/threads/thread-1",
        "/threads/thread-2",
    ]
    assert all(
        params == {"format": "metadata", "metadataHeaders": ["Subject"]}
        for path, params in calls
        if path.startswith("/threads/")
    )


def test_gmail_adapter_surface_has_no_send_capability() -> None:
    source = "\n".join(
        [
            getsource(GmailAuthorizationAdapter),
            getsource(GmailReadAdapter),
            getsource(GmailDraftAdapter),
        ]
    ).casefold()

    assert "/messages/send" not in source
    assert "/drafts/send" not in source
    assert "send_message" not in source
    assert "send_draft" not in source
    assert hasattr(GmailDraftAdapter, "create_reply_draft")
    assert not hasattr(GmailDraftAdapter, "send")


@pytest.mark.parametrize(
    ("method", "url", "authorization_request"),
    [
        ("POST", "https://example.com/token", True),
        ("POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", False),
        ("GET", "http://gmail.googleapis.com/gmail/v1/users/me/profile", False),
        ("GET", "https://gmail.googleapis.com/gmail/v1/users/me/threads/../profile", False),
    ],
)
def test_gmail_transport_rejects_non_allowlisted_credential_endpoints(
    method: str,
    url: str,
    authorization_request: bool,
) -> None:
    transport = GmailTransport(timeout_seconds=1)
    try:
        with pytest.raises(InboxProviderUnavailable, match="endpoint is not allowed"):
            transport.request_json(
                method,
                url,
                access_token=None if authorization_request else "access-token",
                data={"refresh_token": "refresh-token"} if authorization_request else None,
                authorization_request=authorization_request,
            )
    finally:
        transport.close()


@pytest.mark.parametrize("status_code", [429, 503])
def test_gmail_transport_fails_closed_for_rate_limit_and_provider_outage(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    transport = GmailTransport(timeout_seconds=1)
    monkeypatch.setattr(
        transport._client,
        "request",
        lambda *args, **kwargs: httpx.Response(status_code, json={}),
    )
    try:
        with pytest.raises(InboxProviderUnavailable, match=f"status {status_code}"):
            transport.request_json(
                "GET",
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                access_token="access-token",
            )
    finally:
        transport.close()


def test_gmail_transport_requests_reauthorization_for_expired_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = GmailTransport(timeout_seconds=1)
    monkeypatch.setattr(
        transport._client,
        "request",
        lambda *args, **kwargs: httpx.Response(401, json={}),
    )
    try:
        with pytest.raises(InboxAuthorizationError, match="no longer valid"):
            transport.request_json(
                "GET",
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                access_token="expired-access-token",
            )
    finally:
        transport.close()


def test_missing_body_uses_a_fingerprint_of_the_persisted_placeholder() -> None:
    payload = {
        "id": "message-2",
        "threadId": "thread-2",
        "internalDate": str(int(datetime(2026, 8, 12, tzinfo=UTC).timestamp() * 1000)),
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [{"name": "From", "value": "customer@example.com"}],
            "parts": [],
        },
    }

    message = normalize_message(payload, account_address="support@example.com")

    assert message.body == "[Message body unavailable]"
    assert message.sanitized_content_hash == sha256(message.body.encode()).hexdigest()
