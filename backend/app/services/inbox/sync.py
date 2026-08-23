import logging
from datetime import UTC, datetime
from uuid import UUID

from app.domain.identity import ActorContext, Permission
from app.domain.inbox import (
    ExternalConversationRecord,
    InboxAuthorizationError,
    InboxCredentialUnavailable,
    InboxProviderUnavailable,
    InboxSyncDrainResult,
    InboxSyncJobRecord,
    InboxSyncWorkRecord,
    ProviderMessage,
    SyncRequest,
    SyncTrigger,
)
from app.ports.inbox import InboxReadGatewayResolver
from app.ports.inbox_access import InboxAccessProvider
from app.ports.inbox_sync_persistence import (
    InboxSyncUnitOfWork,
    InboxSyncUnitOfWorkFactory,
)
from app.security.authorization import require_permission

logger = logging.getLogger(__name__)


class InboxSyncService:
    def __init__(
        self,
        *,
        unit_of_work: InboxSyncUnitOfWorkFactory,
        gateways: InboxReadGatewayResolver,
        access: InboxAccessProvider,
        page_limit: int = 5,
        item_limit: int = 50,
        manual_item_limit: int = 5,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._gateways = gateways
        self._access = access
        self._page_limit = page_limit
        self._item_limit = item_limit
        self._manual_item_limit = manual_item_limit

    def request_manual(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
        trigger_key: str,
    ) -> InboxSyncJobRecord:
        require_permission(actor, Permission.CONNECTION_MANAGE)
        with self._unit_of_work() as uow:
            return uow.jobs.enqueue(
                organization_public_id=actor.organization_id,
                request=SyncRequest(
                    connection_public_id=connection_id,
                    trigger=SyncTrigger.MANUAL,
                    trigger_key=trigger_key,
                    page_budget=1,
                    item_budget=self._manual_item_limit,
                ),
            )

    def run_manual(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
        trigger_key: str,
        worker_id: str,
    ) -> tuple[InboxSyncJobRecord, InboxSyncDrainResult]:
        job = self.request_manual(
            actor=actor,
            connection_id=connection_id,
            trigger_key=trigger_key,
        )
        result = self.drain(
            worker_id=worker_id,
            limit=1,
            organization_id=actor.organization_id,
            connection_id=connection_id,
        )
        with self._unit_of_work() as uow:
            current = uow.jobs.get(job_id=job.id)
        return current or job, result

    def request_scheduled(
        self,
        *,
        organization_id: str,
        connection_id: str,
        trigger_key: str,
    ) -> InboxSyncJobRecord:
        with self._unit_of_work() as uow:
            return uow.jobs.enqueue(
                organization_public_id=organization_id,
                request=SyncRequest(
                    connection_public_id=connection_id,
                    trigger=SyncTrigger.SCHEDULE,
                    trigger_key=trigger_key,
                    page_budget=self._page_limit,
                    item_budget=self._item_limit,
                ),
            )

    def drain(
        self,
        *,
        worker_id: str,
        limit: int,
        organization_id: str | None = None,
        connection_id: str | None = None,
    ) -> InboxSyncDrainResult:
        with self._unit_of_work() as uow:
            work_items = uow.jobs.claim(
                worker_id=worker_id,
                limit=limit,
                now=datetime.now(UTC),
                organization_public_id=organization_id,
                connection_public_id=connection_id,
            )
        completed = 0
        failed = 0
        imported = 0
        duplicates = 0
        for work in work_items:
            try:
                messages, observed_history_id, next_page_token = self._fetch(work)
                page_imported, page_duplicates = self._persist(
                    work=work,
                    worker_id=worker_id,
                    messages=messages,
                    observed_history_id=observed_history_id,
                    next_page_token=next_page_token,
                )
                completed += 1
                imported += page_imported
                duplicates += page_duplicates
            except InboxAuthorizationError:
                self._fail(
                    work=work,
                    worker_id=worker_id,
                    error_code="authorization_expired",
                    reauthorize=True,
                )
                failed += 1
            except InboxCredentialUnavailable:
                self._fail(
                    work=work,
                    worker_id=worker_id,
                    error_code="credential_unavailable",
                    reauthorize=True,
                )
                failed += 1
            except (InboxProviderUnavailable, LookupError):
                self._fail(
                    work=work,
                    worker_id=worker_id,
                    error_code="provider_unavailable",
                    reauthorize=False,
                )
                failed += 1
            except Exception as exc:
                logger.error(
                    "Unexpected inbox sync failure",
                    extra={
                        "error_type": type(exc).__name__,
                        "job_id": work.job.public_id,
                    },
                )
                self._fail(
                    work=work,
                    worker_id=worker_id,
                    error_code="sync_failed",
                    reauthorize=False,
                )
                failed += 1
        return InboxSyncDrainResult(
            claimed_jobs=len(work_items),
            completed_jobs=completed,
            failed_jobs=failed,
            imported_messages=imported,
            duplicate_messages=duplicates,
        )

    def _fetch(
        self,
        work: InboxSyncWorkRecord,
    ) -> tuple[list[ProviderMessage], str, str | None]:
        start_history_id = work.job.requested_history_id or work.committed_history_id
        if start_history_id is None:
            raise LookupError("The inbox sync history is unavailable.")
        access = self._access.access(
            organization_id=work.organization_public_id,
            connection_id=work.connection_public_id,
        )
        reader = self._gateways.reader(access.adapter_key)
        page_token = work.job.page_token
        observed_history_id = start_history_id
        message_ids: list[str] = []
        for _ in range(work.job.page_budget):
            remaining = work.job.item_budget - len(message_ids)
            if remaining <= 0:
                break
            page = reader.list_changes(
                access=access.access,
                start_history_id=start_history_id,
                page_token=page_token,
                limit=remaining,
            )
            message_ids.extend(page.provider_message_ids)
            observed_history_id = page.history_id
            page_token = page.next_page_token
            if page_token is None:
                break
        messages = [
            reader.get_message(
                access=access.access,
                provider_message_id=message_id,
                account_address=access.account_address,
            )
            for message_id in dict.fromkeys(message_ids[: work.job.item_budget])
        ]
        return messages, observed_history_id, page_token

    def _persist(
        self,
        *,
        work: InboxSyncWorkRecord,
        worker_id: str,
        messages: list[ProviderMessage],
        observed_history_id: str,
        next_page_token: str | None,
    ) -> tuple[int, int]:
        imported = 0
        duplicates = 0
        latest_by_conversation: dict[UUID, tuple[ExternalConversationRecord, ProviderMessage]] = {}
        locked_threads: set[str] = set()
        with self._unit_of_work() as uow:
            for message in sorted(
                messages,
                key=lambda item: (item.received_at, item.provider_message_id),
            ):
                if message.provider_thread_id not in locked_threads:
                    uow.messages.lock_thread(
                        organization_id=work.job.organization_id,
                        connection_id=work.job.connection_id,
                        provider_thread_id=message.provider_thread_id,
                    )
                    locked_threads.add(message.provider_thread_id)
                conversation = uow.messages.get_conversation(
                    organization_id=work.job.organization_id,
                    connection_id=work.job.connection_id,
                    provider_thread_id=message.provider_thread_id,
                )
                if conversation is None:
                    continue
                if uow.messages.has_message(
                    organization_id=work.job.organization_id,
                    connection_id=work.job.connection_id,
                    provider_message_id=message.provider_message_id,
                ):
                    duplicates += 1
                    continue
                case_public_id = uow.cases.case_public_id(
                    organization_public_id=work.organization_public_id,
                    case_id=conversation.case_id,
                )
                local_id = uow.cases.append_message(
                    organization_public_id=work.organization_public_id,
                    case_public_id=case_public_id,
                    thread_id=conversation.thread_id,
                    message=message,
                    correlation_id=f"sync:{work.job.public_id}",
                )
                uow.messages.record_message(
                    organization_id=work.job.organization_id,
                    connection_id=work.job.connection_id,
                    external_conversation_id=conversation.id,
                    local_message_id=local_id,
                    message=message,
                )
                latest_by_conversation[conversation.id] = (conversation, message)
                imported += 1
            self._finalize_conversations(uow, latest_by_conversation)
            uow.jobs.complete(
                job_id=work.job.id,
                worker_id=worker_id,
                observed_history_id=observed_history_id,
                next_page_token=next_page_token,
            )
        return imported, duplicates

    @staticmethod
    def _finalize_conversations(
        uow: InboxSyncUnitOfWork,
        latest: dict[UUID, tuple[ExternalConversationRecord, ProviderMessage]],
    ) -> None:
        for conversation, message in latest.values():
            uow.messages.finalize_conversation(
                conversation_id=conversation.id,
                subject=message.subject,
                latest_message=message,
            )

    def _fail(
        self,
        *,
        work: InboxSyncWorkRecord,
        worker_id: str,
        error_code: str,
        reauthorize: bool,
    ) -> None:
        with self._unit_of_work() as uow:
            uow.jobs.fail(
                job_id=work.job.id,
                worker_id=worker_id,
                error_code=error_code,
                reauthorize=reauthorize,
            )
