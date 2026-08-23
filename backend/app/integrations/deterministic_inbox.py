from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import urlencode

from pydantic import SecretStr

from app.domain.inbox import (
    AccessCredential,
    AuthorizationCallback,
    AuthorizationRequest,
    ChangePage,
    CreateDraftRequest,
    DraftLookupResult,
    DraftLookupStatus,
    DraftReceipt,
    FindDraftRequest,
    GrantedCredential,
    InboxAuthorizationError,
    InboxNotFound,
    MessageAddress,
    MessageDirection,
    ProviderAccount,
    ProviderMessage,
    ProviderThread,
    ProviderThreadSummary,
    RefreshCredential,
    RevocationResult,
    ThreadPage,
)

DETERMINISTIC_INBOX_ADDRESS = "pilot-inbox@example.com"
DETERMINISTIC_PARSER_VERSION = "deterministic-inbox-v1"


class DeterministicInboxGateway:
    provider_name = "deterministic"
    adapter_key = "deterministic_inbox"

    def __init__(
        self,
        *,
        threads: tuple[ProviderThread, ...] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._threads = {
            thread.provider_thread_id: thread
            for thread in (threads or deterministic_threads())
        }
        self._messages = {
            message.provider_message_id: message
            for thread in self._threads.values()
            for message in thread.messages
        }
        self._drafts: dict[str, DraftReceipt] = {}

    def authorization_url(self, request: AuthorizationRequest) -> str:
        return "https://deterministic.invalid/authorize?" + urlencode(
            {
                "client_id": request.client_id,
                "redirect_uri": request.redirect_uri,
                "state": request.state,
                "code_challenge": request.code_challenge,
            }
        )

    def exchange_code(self, callback: AuthorizationCallback) -> GrantedCredential:
        if callback.code.get_secret_value() != "deterministic-code":
            raise InboxAuthorizationError("The deterministic authorization code is invalid.")
        return GrantedCredential(
            access_token=SecretStr("deterministic-access-token"),
            refresh_token=SecretStr("deterministic-refresh-token"),
            granted_scopes=("conversation_read", "draft_create"),
            expires_at=self._clock() + timedelta(hours=1),
        )

    def refresh_access(self, credential: RefreshCredential) -> AccessCredential:
        if credential.refresh_token.get_secret_value() != "deterministic-refresh-token":
            raise InboxAuthorizationError(
                "The deterministic refresh credential is invalid."
            )
        return AccessCredential(
            access_token=SecretStr("deterministic-access-token"),
            expires_at=self._clock() + timedelta(hours=1),
        )

    def revoke(self, credential: RefreshCredential) -> RevocationResult:
        valid = credential.refresh_token.get_secret_value() == "deterministic-refresh-token"
        return RevocationResult(revoked=valid, provider_confirmed=valid)

    def get_account(self, access: AccessCredential) -> ProviderAccount:
        self._require_access(access)
        return ProviderAccount(
            provider_account_id="deterministic-account-1",
            address=DETERMINISTIC_INBOX_ADDRESS,
            history_id=str(len(self._messages)),
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
        self._require_access(access)
        del label_filter
        offset = int(page_token or "0")
        rows = sorted(
            (
                ProviderThreadSummary(
                    provider_thread_id=thread.provider_thread_id,
                    subject=thread.messages[-1].subject,
                    latest_message_at=thread.messages[-1].received_at,
                )
                for thread in self._threads.values()
                if thread.messages[-1].received_at >= after
            ),
            key=lambda item: (item.latest_message_at, item.provider_thread_id),
            reverse=True,
        )
        page = rows[offset : offset + limit]
        next_offset = offset + len(page)
        return ThreadPage(
            items=tuple(page),
            next_page_token=str(next_offset) if next_offset < len(rows) else None,
            history_id=str(len(self._messages)),
        )

    def get_thread(
        self,
        *,
        access: AccessCredential,
        provider_thread_id: str,
        account_address: str = DETERMINISTIC_INBOX_ADDRESS,
    ) -> ProviderThread:
        self._require_access(access)
        if account_address.casefold() != DETERMINISTIC_INBOX_ADDRESS.casefold():
            raise InboxAuthorizationError("The deterministic inbox account is invalid.")
        try:
            return self._threads[provider_thread_id]
        except KeyError as exc:
            raise InboxNotFound("The deterministic inbox thread was not found.") from exc

    def list_changes(
        self,
        *,
        access: AccessCredential,
        start_history_id: str,
        page_token: str | None,
        limit: int,
    ) -> ChangePage:
        self._require_access(access)
        offset = int(page_token or start_history_id)
        message_ids = sorted(self._messages)
        page = message_ids[offset : offset + limit]
        next_offset = offset + len(page)
        return ChangePage(
            provider_message_ids=tuple(page),
            next_page_token=(str(next_offset) if next_offset < len(message_ids) else None),
            history_id=str(len(message_ids)),
        )

    def get_message(
        self,
        *,
        access: AccessCredential,
        provider_message_id: str,
        account_address: str = DETERMINISTIC_INBOX_ADDRESS,
    ) -> ProviderMessage:
        self._require_access(access)
        if account_address.casefold() != DETERMINISTIC_INBOX_ADDRESS.casefold():
            raise InboxAuthorizationError("The deterministic inbox account is invalid.")
        try:
            return self._messages[provider_message_id]
        except KeyError as exc:
            raise InboxNotFound("The deterministic inbox message was not found.") from exc

    def create_reply_draft(
        self,
        *,
        access: AccessCredential,
        request: CreateDraftRequest,
    ) -> DraftReceipt:
        self._require_access(access)
        existing = self._drafts.get(request.correlation_key)
        if existing is not None:
            return existing
        digest = sha256(request.correlation_key.encode()).hexdigest()[:16]
        receipt = DraftReceipt(
            provider_draft_id=f"draft-{digest}",
            provider_message_id=f"message-{digest}",
            provider_thread_id=request.provider_thread_id,
            created_at=self._clock(),
        )
        self._drafts[request.correlation_key] = receipt
        return receipt

    def find_draft(
        self,
        *,
        access: AccessCredential,
        request: FindDraftRequest,
    ) -> DraftLookupResult:
        self._require_access(access)
        receipt = self._drafts.get(request.correlation_key)
        return DraftLookupResult(
            status=(
                DraftLookupStatus.FOUND
                if receipt is not None
                else DraftLookupStatus.ABSENT
            ),
            receipt=receipt,
            absence_is_terminal=receipt is None,
        )

    def close(self) -> None:
        return None

    @staticmethod
    def _require_access(access: AccessCredential) -> None:
        if access.access_token.get_secret_value() != "deterministic-access-token":
            raise InboxAuthorizationError("The deterministic access credential is invalid.")


def deterministic_threads() -> tuple[ProviderThread, ...]:
    customer = MessageAddress(address="nadia@example.com", name="Nadia")
    inbox = MessageAddress(address=DETERMINISTIC_INBOX_ADDRESS, name="Support")
    first_body = "I was charged twice for invoice INV-78412. Please help me check it."
    first = _message(
        message_id="msg-001",
        thread_id="thread-billing-001",
        subject="Duplicate charge on INV-78412",
        sender=customer,
        recipients=(inbox,),
        direction=MessageDirection.INBOUND,
        received_at=datetime(2026, 8, 12, 1, 0, tzinfo=UTC),
        body=first_body,
    )
    reply_body = "We are checking the two payment records and will update you."
    reply = _message(
        message_id="msg-002",
        thread_id="thread-billing-001",
        subject="Re: Duplicate charge on INV-78412",
        sender=inbox,
        recipients=(customer,),
        direction=MessageDirection.OUTBOUND,
        received_at=datetime(2026, 8, 12, 1, 10, tzinfo=UTC),
        body=reply_body,
    )
    return (
        ProviderThread(
            provider_thread_id="thread-billing-001",
            history_id="2",
            messages=(first, reply),
        ),
    )


def _message(
    *,
    message_id: str,
    thread_id: str,
    subject: str,
    sender: MessageAddress,
    recipients: tuple[MessageAddress, ...],
    direction: MessageDirection,
    received_at: datetime,
    body: str,
) -> ProviderMessage:
    content_hash = sha256(body.encode()).hexdigest()
    return ProviderMessage(
        provider_message_id=message_id,
        provider_thread_id=thread_id,
        rfc_message_id=f"<{message_id}@example.com>",
        subject=subject,
        sender=sender,
        recipients=recipients,
        direction=direction,
        received_at=received_at,
        body=body,
        sanitized_content_hash=content_hash,
        raw_source_hash=content_hash,
        parser_version=DETERMINISTIC_PARSER_VERSION,
    )
