from uuid import UUID

from app.domain.identity import ActorContext, Permission
from app.domain.inbox import (
    InboxConflict,
    InboxImportMode,
    InboxImportResult,
    ProviderMessage,
    SelectedThreadImportCommand,
)
from app.ports.inbox import InboxReadGatewayResolver
from app.ports.inbox_access import InboxAccessProvider
from app.ports.inbox_import_persistence import (
    InboxImportUnitOfWork,
    InboxImportUnitOfWorkFactory,
)
from app.security.authorization import require_permission


class InboxImportService:
    def __init__(
        self,
        *,
        unit_of_work: InboxImportUnitOfWorkFactory,
        gateways: InboxReadGatewayResolver,
        access: InboxAccessProvider,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._gateways = gateways
        self._access = access

    def import_selected_thread(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
        command: SelectedThreadImportCommand,
        correlation_id: str,
    ) -> InboxImportResult:
        require_permission(actor, Permission.CASE_MANAGE)
        require_permission(actor, Permission.CONNECTION_READ)
        access = self._access.access(
            organization_id=actor.organization_id,
            connection_id=connection_id,
        )
        if access.import_mode == InboxImportMode.PAUSED.value:
            raise InboxConflict("Inbox import is paused.")
        thread = self._gateways.reader(access.adapter_key).get_thread(
            access=access.access,
            provider_thread_id=command.provider_thread_id,
            account_address=access.account_address,
        )
        messages = sorted(
            thread.messages,
            key=lambda item: (item.received_at, item.provider_message_id),
        )
        with self._unit_of_work() as uow:
            uow.messages.lock_thread(
                organization_id=access.organization_id,
                connection_id=access.connection_id,
                provider_thread_id=thread.provider_thread_id,
            )
            conversation = uow.messages.get_conversation(
                organization_id=access.organization_id,
                connection_id=access.connection_id,
                provider_thread_id=thread.provider_thread_id,
            )
            first_local_message_id = None
            if conversation is None:
                handle = uow.cases.create_case(
                    organization_public_id=actor.organization_id,
                    connection_public_id=connection_id,
                    thread=thread,
                    command=command,
                    correlation_id=correlation_id,
                )
                conversation = uow.messages.create_conversation(
                    organization_id=access.organization_id,
                    connection_id=access.connection_id,
                    case=handle,
                    first_message=messages[0],
                )
                case_public_id = handle.case_public_id
                first_local_message_id = handle.first_local_message_id
            else:
                case_public_id = uow.cases.case_public_id(
                    organization_public_id=actor.organization_id,
                    case_id=conversation.case_id,
                )

            imported = 0
            duplicates = 0
            for index, message in enumerate(messages):
                if uow.messages.has_message(
                    organization_id=access.organization_id,
                    connection_id=access.connection_id,
                    provider_message_id=message.provider_message_id,
                ):
                    duplicates += 1
                    continue
                local_message_id = self._local_message_id(
                    uow=uow,
                    actor=actor,
                    case_public_id=case_public_id,
                    thread_id=conversation.thread_id,
                    message=message,
                    initial_id=first_local_message_id if index == 0 else None,
                    correlation_id=correlation_id,
                )
                uow.messages.record_message(
                    organization_id=access.organization_id,
                    connection_id=access.connection_id,
                    external_conversation_id=conversation.id,
                    local_message_id=local_message_id,
                    message=message,
                )
                imported += 1
            if imported:
                conversation = uow.messages.finalize_conversation(
                    conversation_id=conversation.id,
                    subject=messages[-1].subject,
                    latest_message=messages[-1],
                )
        return InboxImportResult(
            case_public_id=case_public_id,
            external_conversation_public_id=conversation.public_id,
            imported_messages=imported,
            duplicate_messages=duplicates,
            conversation_fingerprint=conversation.source_fingerprint,
            latest_message_at=conversation.latest_message_at,
        )

    @staticmethod
    def _local_message_id(
        *,
        uow: InboxImportUnitOfWork,
        actor: ActorContext,
        case_public_id: str,
        thread_id: UUID,
        message: ProviderMessage,
        initial_id: UUID | None,
        correlation_id: str,
    ) -> UUID:
        if initial_id is not None:
            return initial_id
        return uow.cases.append_message(
            organization_public_id=actor.organization_id,
            case_public_id=case_public_id,
            thread_id=thread_id,
            message=message,
            correlation_id=correlation_id,
        )
