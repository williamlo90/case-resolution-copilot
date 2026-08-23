from base64 import urlsafe_b64encode
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage
from hashlib import sha256
from typing import Any

from app.domain.inbox import (
    AccessCredential,
    CreateDraftRequest,
    DraftLookupResult,
    DraftLookupStatus,
    DraftReceipt,
    FindDraftRequest,
    InboxProviderUnavailable,
)

from .normalization import header_values, normalize_message
from .read import GMAIL_API_ROOT, _dict_rows, _optional_text, _text
from .transport import GmailTransport

CORRELATION_HEADER = "X-Case-Resolution-Correlation"
MAX_RECONCILIATION_CANDIDATES = 25


class GmailDraftAdapter:
    provider_name = "gmail"

    def __init__(
        self,
        *,
        timeout_seconds: float,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = GmailTransport(timeout_seconds=timeout_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_reply_draft(
        self,
        *,
        access: AccessCredential,
        request: CreateDraftRequest,
    ) -> DraftReceipt:
        payload = self._transport.request_json(
            "POST",
            GMAIL_API_ROOT + "/drafts",
            access_token=access.access_token.get_secret_value(),
            json={
                "message": {
                    "threadId": request.provider_thread_id,
                    "raw": _encoded_message(request),
                }
            },
        )
        message = payload.get("message")
        if not isinstance(message, dict):
            raise InboxProviderUnavailable("The inbox draft response is incomplete.")
        return DraftReceipt(
            provider_draft_id=_text(payload, "id"),
            provider_message_id=_text(message, "id"),
            provider_thread_id=_text(message, "threadId"),
            created_at=self._clock(),
        )

    def find_draft(
        self,
        *,
        access: AccessCredential,
        request: FindDraftRequest,
    ) -> DraftLookupResult:
        payload = self._transport.request_json(
            "GET",
            GMAIL_API_ROOT + "/drafts",
            access_token=access.access_token.get_secret_value(),
            params={"maxResults": MAX_RECONCILIATION_CANDIDATES},
        )
        matches: list[DraftReceipt] = []
        for row in _dict_rows(payload, "drafts")[:MAX_RECONCILIATION_CANDIDATES]:
            detail = self._transport.request_json(
                "GET",
                GMAIL_API_ROOT + f"/drafts/{_text(row, 'id')}",
                access_token=access.access_token.get_secret_value(),
                params={"format": "full"},
            )
            try:
                receipt = _matching_receipt(
                    detail,
                    request=request,
                    provider_draft_id=_text(row, "id"),
                )
            except InboxProviderUnavailable:
                continue
            if receipt is not None:
                matches.append(receipt)
        if len(matches) == 1:
            return DraftLookupResult(status=DraftLookupStatus.FOUND, receipt=matches[0])
        if len(matches) > 1:
            return DraftLookupResult(status=DraftLookupStatus.AMBIGUOUS)
        return DraftLookupResult(status=DraftLookupStatus.ABSENT)

    def close(self) -> None:
        self._transport.close()


def _encoded_message(request: CreateDraftRequest) -> str:
    message = EmailMessage()
    message["To"] = request.recipient
    message["Subject"] = request.subject
    message[CORRELATION_HEADER] = request.correlation_key
    if request.in_reply_to:
        message["In-Reply-To"] = request.in_reply_to
    if request.references:
        message["References"] = " ".join(request.references)
    message.set_content(request.body)
    return urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")


def _matching_receipt(
    payload: dict[str, Any],
    *,
    request: FindDraftRequest,
    provider_draft_id: str,
) -> DraftReceipt | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    if _text(message, "threadId") != request.provider_thread_id:
        return None
    headers = header_values(message)
    correlation = headers.get(CORRELATION_HEADER.casefold())
    received_at = _draft_time(message)
    if received_at < request.not_before:
        return None
    if correlation != request.correlation_key:
        try:
            normalized = normalize_message(
                message,
                account_address="draft-owner@example.invalid",
            )
        except InboxProviderUnavailable:
            return None
        if (
            headers.get("to", "").casefold() != request.recipient.casefold()
            or headers.get("subject") != request.subject
            or sha256(normalized.body.encode("utf-8")).hexdigest() != request.body_hash
        ):
            return None
    return DraftReceipt(
        provider_draft_id=provider_draft_id,
        provider_message_id=_text(message, "id"),
        provider_thread_id=request.provider_thread_id,
        created_at=received_at,
    )


def _draft_time(message: dict[str, Any]) -> datetime:
    internal_date = _optional_text(message, "internalDate")
    if internal_date is None or not internal_date.isdigit():
        raise InboxProviderUnavailable("The inbox draft timestamp is invalid.")
    return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
