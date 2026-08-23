from datetime import datetime
from typing import Protocol

from app.domain.inbox import (
    AccessCredential,
    AuthorizationCallback,
    AuthorizationRequest,
    ChangePage,
    CreateDraftRequest,
    DraftLookupResult,
    DraftReceipt,
    FindDraftRequest,
    GrantedCredential,
    ProviderAccount,
    ProviderMessage,
    ProviderThread,
    RefreshCredential,
    RevocationResult,
    ThreadPage,
)


class InboxAuthorizationGateway(Protocol):
    provider_name: str

    def authorization_url(self, request: AuthorizationRequest) -> str: ...

    def exchange_code(self, callback: AuthorizationCallback) -> GrantedCredential: ...

    def refresh_access(self, credential: RefreshCredential) -> AccessCredential: ...

    def revoke(self, credential: RefreshCredential) -> RevocationResult: ...


class InboxReadGateway(Protocol):
    provider_name: str

    def get_account(self, access: AccessCredential) -> ProviderAccount: ...

    def list_threads(
        self,
        *,
        access: AccessCredential,
        label_filter: tuple[str, ...],
        after: datetime,
        page_token: str | None,
        limit: int,
    ) -> ThreadPage: ...

    def get_thread(
        self,
        *,
        access: AccessCredential,
        provider_thread_id: str,
        account_address: str,
    ) -> ProviderThread: ...

    def list_changes(
        self,
        *,
        access: AccessCredential,
        start_history_id: str,
        page_token: str | None,
        limit: int,
    ) -> ChangePage: ...

    def get_message(
        self,
        *,
        access: AccessCredential,
        provider_message_id: str,
        account_address: str,
    ) -> ProviderMessage: ...


class InboxDraftGateway(Protocol):
    provider_name: str

    def create_reply_draft(
        self,
        *,
        access: AccessCredential,
        request: CreateDraftRequest,
    ) -> DraftReceipt: ...

    def find_draft(
        self,
        *,
        access: AccessCredential,
        request: FindDraftRequest,
    ) -> DraftLookupResult: ...


class InboxAuthorizationGatewayResolver(Protocol):
    def authorization(self, adapter_key: str) -> InboxAuthorizationGateway: ...

    def reader(self, adapter_key: str) -> InboxReadGateway: ...


class InboxAccessGatewayResolver(Protocol):
    def authorization(self, adapter_key: str) -> InboxAuthorizationGateway: ...


class InboxReadGatewayResolver(Protocol):
    def reader(self, adapter_key: str) -> InboxReadGateway: ...


class InboxDraftGatewayResolver(Protocol):
    def drafts(self, adapter_key: str) -> InboxDraftGateway: ...
