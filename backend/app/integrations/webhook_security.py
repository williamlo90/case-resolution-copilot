import hmac
from datetime import UTC, datetime
from hashlib import sha256

TIMESTAMP_HEADER = "X-Support-Copilot-Timestamp"
SIGNATURE_HEADER = "X-Support-Copilot-Signature"
SIGNATURE_VERSION = "v1"


class WebhookSignatureError(ValueError):
    pass


def sign_webhook(*, secret: str, timestamp: int, body: bytes) -> str:
    payload = str(timestamp).encode("ascii") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), payload, sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def verify_webhook(
    *,
    secret: str,
    timestamp_header: str | None,
    signature_header: str | None,
    body: bytes,
    max_age_seconds: int,
    now: datetime | None = None,
) -> None:
    try:
        timestamp = int(timestamp_header or "")
    except ValueError as exc:
        raise WebhookSignatureError("The webhook could not be verified.") from exc

    current = now or datetime.now(UTC)
    if current.utcoffset() is None:
        raise ValueError("Webhook verification clock must be timezone-aware.")
    if abs(int(current.timestamp()) - timestamp) > max_age_seconds:
        raise WebhookSignatureError("The webhook could not be verified.")

    expected = sign_webhook(secret=secret, timestamp=timestamp, body=body)
    if not signature_header or not hmac.compare_digest(expected, signature_header):
        raise WebhookSignatureError("The webhook could not be verified.")
