import json
import re
from base64 import urlsafe_b64decode
from datetime import UTC, datetime
from email.utils import getaddresses
from hashlib import sha256
from html.parser import HTMLParser
from typing import Any

from app.domain.inbox import (
    AttachmentContentStatus,
    InboxProviderUnavailable,
    MessageAddress,
    MessageDirection,
    ProviderAttachment,
    ProviderMessage,
)

PARSER_VERSION = "gmail-mime-v1"
MAX_MIME_DEPTH = 10
MAX_BODY_BYTES = 100_000


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._parts)).strip()


def normalize_message(
    payload: dict[str, Any],
    *,
    account_address: str,
) -> ProviderMessage:
    message_id = _required_text(payload, "id")
    thread_id = _required_text(payload, "threadId")
    message_payload = payload.get("payload")
    if not isinstance(message_payload, dict):
        raise InboxProviderUnavailable("The inbox message has no MIME payload.")
    headers = _headers(message_payload)
    sender = _single_address(headers.get("from", ""))
    recipients = _addresses(headers.get("to", ""))[:50]
    body, omission_reason = _body(message_payload, depth=0)
    attachments = tuple(_attachments(message_payload, depth=0))[:25]
    received_at = _received_at(payload)
    normalized_body = body or "[Message body unavailable]"
    raw_hash = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ProviderMessage(
        provider_message_id=message_id,
        provider_thread_id=thread_id,
        rfc_message_id=headers.get("message-id"),
        subject=(headers.get("subject") or "(No subject)")[:500],
        sender=sender,
        recipients=tuple(recipients),
        direction=(
            MessageDirection.OUTBOUND
            if sender.address.casefold() == account_address.casefold()
            else MessageDirection.INBOUND
        ),
        received_at=received_at,
        body=normalized_body,
        sanitized_content_hash=sha256(normalized_body.encode("utf-8")).hexdigest(),
        raw_source_hash=raw_hash,
        parser_version=PARSER_VERSION,
        omission_reason=omission_reason,
        attachments=attachments,
    )


def header_values(payload: dict[str, Any]) -> dict[str, str]:
    message_payload = payload.get("payload")
    return _headers(message_payload) if isinstance(message_payload, dict) else {}


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    rows = payload.get("headers", [])
    if not isinstance(rows, list):
        return values
    for row in rows[:100]:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        value = row.get("value")
        if isinstance(name, str) and isinstance(value, str):
            values[name.casefold()] = value[:4000]
    return values


def _single_address(value: str) -> MessageAddress:
    addresses = _addresses(value)
    if not addresses:
        return MessageAddress(address="unknown@example.invalid", name="Unknown sender")
    return addresses[0]


def _addresses(value: str) -> list[MessageAddress]:
    return [
        MessageAddress(address=address.casefold(), name=name or None)
        for name, address in getaddresses([value])
        if address and "@" in address
    ]


def _body(payload: dict[str, Any], *, depth: int) -> tuple[str, str | None]:
    if depth > MAX_MIME_DEPTH:
        return "", "MIME structure exceeded the supported depth."
    mime_type = payload.get("mimeType")
    own_body = payload.get("body")
    if mime_type in {"text/plain", "text/html"} and isinstance(own_body, dict):
        encoded = own_body.get("data")
        if isinstance(encoded, str) and encoded:
            decoded, truncated = _decode(encoded)
            text = decoded.decode("utf-8", errors="replace")
            if mime_type == "text/html":
                parser = _TextExtractor()
                parser.feed(text)
                text = parser.text()
            return text.strip(), "Message body was truncated." if truncated else None
    parts = payload.get("parts", [])
    if not isinstance(parts, list):
        return "", "Message body was unavailable."
    plain: list[tuple[str, str | None]] = []
    html: list[tuple[str, str | None]] = []
    for part in parts[:50]:
        if not isinstance(part, dict):
            continue
        candidate = _body(part, depth=depth + 1)
        if not candidate[0]:
            continue
        (plain if part.get("mimeType") == "text/plain" else html).append(candidate)
    candidates = plain or html
    return candidates[0] if candidates else ("", "Message body was unavailable.")


def _attachments(payload: dict[str, Any], *, depth: int) -> list[ProviderAttachment]:
    if depth > MAX_MIME_DEPTH:
        return []
    result: list[ProviderAttachment] = []
    filename = payload.get("filename")
    body = payload.get("body")
    if isinstance(filename, str) and filename and isinstance(body, dict):
        attachment_id = body.get("attachmentId")
        size = body.get("size", 0)
        if isinstance(attachment_id, str) and isinstance(size, int):
            result.append(
                ProviderAttachment(
                    provider_attachment_id=attachment_id,
                    name=filename[:500],
                    media_type=str(payload.get("mimeType") or "application/octet-stream")[:200],
                    reported_size=max(0, min(size, 100_000_000)),
                    content_status=AttachmentContentStatus.METADATA_ONLY,
                )
            )
    parts = payload.get("parts", [])
    if isinstance(parts, list):
        for part in parts[:50]:
            if isinstance(part, dict):
                result.extend(_attachments(part, depth=depth + 1))
    return result


def _decode(value: str) -> tuple[bytes, bool]:
    try:
        decoded = urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except ValueError:
        return b"", False
    return decoded[:MAX_BODY_BYTES], len(decoded) > MAX_BODY_BYTES


def _received_at(payload: dict[str, Any]) -> datetime:
    value = payload.get("internalDate")
    if not isinstance(value, str) or not value.isdigit():
        raise InboxProviderUnavailable("The inbox message timestamp is invalid.")
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise InboxProviderUnavailable("The inbox message response is incomplete.")
    return value
