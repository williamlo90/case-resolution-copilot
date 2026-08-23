from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from hashlib import sha256
from inspect import getsource

import pytest

from app.domain.inbox import AuthorizationRequest, InboxProviderUnavailable
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
