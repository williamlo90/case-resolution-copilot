from datetime import UTC, datetime

import pytest

from app.integrations.webhook_security import (
    WebhookSignatureError,
    sign_webhook,
    verify_webhook,
)

SECRET = "test-signing-secret-with-at-least-32-characters"
NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
TIMESTAMP = int(NOW.timestamp())
BODY = b'{"event_id":"case-123"}'


def test_webhook_signature_accepts_an_exact_recent_body() -> None:
    verify_webhook(
        secret=SECRET,
        timestamp_header=str(TIMESTAMP),
        signature_header=sign_webhook(
            secret=SECRET,
            timestamp=TIMESTAMP,
            body=BODY,
        ),
        body=BODY,
        max_age_seconds=300,
        now=NOW,
    )


@pytest.mark.parametrize(
    ("timestamp_header", "signature_header", "body"),
    [
        ("invalid", "v1=invalid", BODY),
        (str(TIMESTAMP), "v1=invalid", BODY),
        (
            str(TIMESTAMP),
            sign_webhook(secret=SECRET, timestamp=TIMESTAMP, body=BODY),
            b'{"event_id":"case-124"}',
        ),
        (
            str(TIMESTAMP - 301),
            sign_webhook(secret=SECRET, timestamp=TIMESTAMP - 301, body=BODY),
            BODY,
        ),
    ],
)
def test_webhook_signature_rejects_invalid_or_stale_requests(
    timestamp_header: str,
    signature_header: str,
    body: bytes,
) -> None:
    with pytest.raises(WebhookSignatureError, match="could not be verified"):
        verify_webhook(
            secret=SECRET,
            timestamp_header=timestamp_header,
            signature_header=signature_header,
            body=body,
            max_age_seconds=300,
            now=NOW,
        )
