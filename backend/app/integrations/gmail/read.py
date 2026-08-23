from datetime import UTC, datetime
from typing import Any

from app.domain.inbox import (
    AccessCredential,
    ChangePage,
    InboxProviderUnavailable,
    ProviderAccount,
    ProviderMessage,
    ProviderThread,
    ProviderThreadSummary,
    ThreadPage,
)

from .normalization import header_values, normalize_message
from .transport import GmailTransport

GMAIL_API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailReadAdapter:
    provider_name = "gmail"

    def __init__(self, *, timeout_seconds: float) -> None:
        self._transport = GmailTransport(timeout_seconds=timeout_seconds)

    def get_account(self, access: AccessCredential) -> ProviderAccount:
        payload = self._get("/profile", access=access)
        return ProviderAccount(
            provider_account_id=_text(payload, "emailAddress").casefold(),
            address=_text(payload, "emailAddress").casefold(),
            history_id=_optional_text(payload, "historyId"),
        )

    def list_threads(
        self,
        *,
        access: AccessCredential,
        label_filter: tuple[str, ...],
        after: datetime,
        page_token: str | None,
        limit: int,
    ) -> ThreadPage:
        params: dict[str, str | int | list[str]] = {
            "labelIds": list(label_filter),
            "maxResults": min(limit, 100),
            "q": f"after:{int(after.timestamp())}",
        }
        if page_token:
            params["pageToken"] = page_token
        payload = self._get("/threads", access=access, params=params)
        summaries: list[ProviderThreadSummary] = []
        for row in _dict_rows(payload, "threads")[:limit]:
            thread_id = _text(row, "id")
            thread = self._get(
                f"/threads/{thread_id}",
                access=access,
                params={"format": "metadata", "metadataHeaders": ["Subject"]},
            )
            messages = _dict_rows(thread, "messages")
            if not messages:
                continue
            summaries.append(_thread_summary(thread_id, messages[-1]))
        return ThreadPage(
            items=tuple(summaries),
            next_page_token=_optional_text(payload, "nextPageToken"),
            history_id=_optional_text(payload, "historyId"),
        )

    def get_thread(
        self,
        *,
        access: AccessCredential,
        provider_thread_id: str,
        account_address: str,
    ) -> ProviderThread:
        payload = self._get(
            f"/threads/{provider_thread_id}",
            access=access,
            params={"format": "full"},
        )
        messages = tuple(
            normalize_message(row, account_address=account_address)
            for row in _dict_rows(payload, "messages")[:100]
        )
        if not messages:
            raise InboxProviderUnavailable("The inbox thread contains no messages.")
        return ProviderThread(
            provider_thread_id=provider_thread_id,
            history_id=_optional_text(payload, "historyId"),
            messages=messages,
        )

    def list_changes(
        self,
        *,
        access: AccessCredential,
        start_history_id: str,
        page_token: str | None,
        limit: int,
    ) -> ChangePage:
        params: dict[str, str | int | list[str]] = {
            "historyTypes": ["messageAdded"],
            "maxResults": min(limit, 100),
            "startHistoryId": start_history_id,
        }
        if page_token:
            params["pageToken"] = page_token
        payload = self._get("/history", access=access, params=params)
        message_ids: list[str] = []
        for history in _dict_rows(payload, "history"):
            for added in _dict_rows(history, "messagesAdded"):
                message = added.get("message")
                if isinstance(message, dict):
                    message_ids.append(_text(message, "id"))
        return ChangePage(
            provider_message_ids=tuple(dict.fromkeys(message_ids[:limit])),
            next_page_token=_optional_text(payload, "nextPageToken"),
            history_id=_text(payload, "historyId"),
        )

    def get_message(
        self,
        *,
        access: AccessCredential,
        provider_message_id: str,
        account_address: str,
    ) -> ProviderMessage:
        return normalize_message(
            self._get(
                f"/messages/{provider_message_id}",
                access=access,
                params={"format": "full"},
            ),
            account_address=account_address,
        )

    def close(self) -> None:
        self._transport.close()

    def _get(
        self,
        path: str,
        *,
        access: AccessCredential,
        params: dict[str, str | int | list[str]] | None = None,
    ) -> dict[str, Any]:
        return self._transport.request_json(
            "GET",
            GMAIL_API_ROOT + path,
            access_token=access.access_token.get_secret_value(),
            params=params,
        )


def _dict_rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _thread_summary(
    provider_thread_id: str,
    latest_message: dict[str, Any],
) -> ProviderThreadSummary:
    timestamp = _text(latest_message, "internalDate")
    if not timestamp.isdigit():
        raise InboxProviderUnavailable("The inbox message timestamp is invalid.")
    subject = header_values(latest_message).get("subject") or "(No subject)"
    return ProviderThreadSummary(
        provider_thread_id=provider_thread_id,
        subject=subject[:500],
        latest_message_at=datetime.fromtimestamp(int(timestamp) / 1000, tz=UTC),
    )


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise InboxProviderUnavailable("The inbox provider response is incomplete.")
    return value


def _optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None
