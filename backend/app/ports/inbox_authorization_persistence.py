from datetime import datetime
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.domain.connections import ConnectionRecord
from app.domain.inbox import (
    EncryptedCredential,
    InboxCapability,
    InboxConnectionProfileRecord,
    InboxCredentialRecord,
    InboxImportMode,
    OAuthSessionRecord,
    ProviderAccount,
)


class InboxOAuthSessionStore(Protocol):
    def create(
        self,
        *,
        organization_public_id: str,
        actor_public_id: str,
        session_public_id: str,
        provider: str,
        capabilities: tuple[InboxCapability, ...],
        return_path: str,
        state: str,
        verifier: EncryptedCredential,
        expires_at: datetime,
    ) -> OAuthSessionRecord: ...

    def consume(
        self,
        *,
        organization_public_id: str,
        actor_public_id: str,
        state: str,
        now: datetime,
    ) -> OAuthSessionRecord: ...


class InboxCredentialStore(Protocol):
    def establish(
        self,
        *,
        connection: ConnectionRecord,
        account: ProviderAccount,
        provider: str,
        granted_scopes: tuple[str, ...],
        credential: EncryptedCredential,
        initial_window_days: int,
        initial_item_limit: int,
        actor_id: str,
        correlation_id: str,
    ) -> InboxConnectionProfileRecord: ...

    def get(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> InboxCredentialRecord: ...

    def set_import_mode(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
        mode: InboxImportMode,
        actor_id: str,
        correlation_id: str,
    ) -> InboxConnectionProfileRecord: ...

    def delete_credential(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
        actor_id: str,
        correlation_id: str,
    ) -> None: ...


class InboxConnectionStore(Protocol):
    def connect(
        self,
        *,
        organization_id: UUID,
        account_address: str,
        provider_account_id: str,
        adapter_key: str,
        read_capabilities: list[str],
        write_capabilities: list[str],
    ) -> ConnectionRecord: ...

    def disconnect(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> ConnectionRecord: ...


class InboxAuthorizationUnitOfWork(Protocol):
    oauth_sessions: InboxOAuthSessionStore
    credentials: InboxCredentialStore
    connections: InboxConnectionStore

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class InboxAuthorizationUnitOfWorkFactory(Protocol):
    def __call__(self) -> InboxAuthorizationUnitOfWork: ...
