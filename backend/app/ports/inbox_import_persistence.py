from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.domain.inbox import (
    ExternalConversationRecord,
    ExternalMessageRecord,
    ImportedCaseHandle,
    ProviderMessage,
    ProviderThread,
    SelectedThreadImportCommand,
)


class InboxCaseWriter(Protocol):
    def case_public_id(
        self,
        *,
        organization_public_id: str,
        case_id: UUID,
    ) -> str: ...

    def create_case(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
        thread: ProviderThread,
        command: SelectedThreadImportCommand,
        correlation_id: str,
    ) -> ImportedCaseHandle: ...

    def append_message(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        thread_id: UUID,
        message: ProviderMessage,
        correlation_id: str,
    ) -> UUID: ...


class InboxMessageStore(Protocol):
    def lock_thread(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        provider_thread_id: str,
    ) -> None: ...

    def get_conversation(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        provider_thread_id: str,
    ) -> ExternalConversationRecord | None: ...

    def create_conversation(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        case: ImportedCaseHandle,
        first_message: ProviderMessage,
    ) -> ExternalConversationRecord: ...

    def has_message(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        provider_message_id: str,
    ) -> bool: ...

    def record_message(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        external_conversation_id: UUID,
        local_message_id: UUID,
        message: ProviderMessage,
    ) -> ExternalMessageRecord: ...

    def finalize_conversation(
        self,
        *,
        conversation_id: UUID,
        subject: str,
        latest_message: ProviderMessage,
    ) -> ExternalConversationRecord: ...


class InboxImportUnitOfWork(Protocol):
    cases: InboxCaseWriter
    messages: InboxMessageStore

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class InboxImportUnitOfWorkFactory(Protocol):
    def __call__(self) -> InboxImportUnitOfWork: ...
