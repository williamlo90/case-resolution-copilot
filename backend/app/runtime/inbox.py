from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256

from app.config import Settings
from app.domain.inbox import InboxCapability
from app.integrations.deterministic_inbox import DeterministicInboxGateway
from app.integrations.gmail import (
    GmailAuthorizationAdapter,
    GmailDraftAdapter,
    GmailReadAdapter,
)
from app.integrations.gmail.oauth import GMAIL_DRAFT_SCOPE, GMAIL_READ_SCOPE
from app.integrations.inbox_gateway import InboxAdapter, InboxGatewayRegistry
from app.persistence.database import Database
from app.persistence.inbox.authorization_uow import (
    SqlAlchemyInboxAuthorizationUnitOfWorkFactory,
)
from app.persistence.inbox.draft_uow import SqlAlchemyInboxDraftUnitOfWorkFactory
from app.persistence.inbox.import_uow import SqlAlchemyInboxImportUnitOfWorkFactory
from app.persistence.inbox.sync_uow import SqlAlchemyInboxSyncUnitOfWorkFactory
from app.security.credential_vault import AesGcmCredentialVault
from app.services.inbox.access import InboxAccessService
from app.services.inbox.authorization import (
    InboxAuthorizationPolicy,
    InboxAuthorizationService,
)
from app.services.inbox.browse import InboxBrowseService
from app.services.inbox.connection_controls import InboxConnectionControlService
from app.services.inbox.draft_delivery import InboxDraftDeliveryService
from app.services.inbox.imports import InboxImportService
from app.services.inbox.sync import InboxSyncService


@dataclass(frozen=True, slots=True)
class InboxRuntime:
    authorization: InboxAuthorizationService
    browse: InboxBrowseService
    controls: InboxConnectionControlService
    imports: InboxImportService
    sync: InboxSyncService
    drafts: InboxDraftDeliveryService
    close: Callable[[], None]


def build_inbox_runtime(
    *,
    database: Database | None,
    settings: Settings,
    sync_lease_seconds: int = 60,
) -> InboxRuntime | None:
    if database is None or not settings.inbox_connections_enabled:
        return None
    registry, adapter_key, client_id, redirect_uri = _gateway_registry(settings)
    vault = AesGcmCredentialVault(
        key=_vault_key(settings),
        key_id=settings.credential_vault_key_id,
    )
    authorization_uow = SqlAlchemyInboxAuthorizationUnitOfWorkFactory(database)
    access = InboxAccessService(
        unit_of_work=authorization_uow,
        gateways=registry,
        credentials=vault,
    )
    authorization = InboxAuthorizationService(
        unit_of_work=authorization_uow,
        gateways=registry,
        credentials=vault,
        policy=InboxAuthorizationPolicy(
            adapter_key=adapter_key,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope_by_capability=_scopes(settings),
            initial_window_days=settings.inbox_initial_window_days,
            initial_item_limit=settings.inbox_initial_item_limit,
            drafts_enabled=settings.inbox_draft_writeback_enabled,
        ),
    )
    controls = InboxConnectionControlService(
        unit_of_work=authorization_uow,
        gateways=registry,
        credentials=vault,
        access=access,
    )
    return InboxRuntime(
        authorization=authorization,
        browse=InboxBrowseService(
            gateways=registry,
            access=access,
            window_days=settings.inbox_initial_window_days,
            item_limit=settings.inbox_initial_item_limit,
        ),
        controls=controls,
        imports=InboxImportService(
            unit_of_work=SqlAlchemyInboxImportUnitOfWorkFactory(database),
            gateways=registry,
            access=access,
        ),
        sync=InboxSyncService(
            unit_of_work=SqlAlchemyInboxSyncUnitOfWorkFactory(database),
            gateways=registry,
            access=access,
            page_limit=5,
            item_limit=settings.inbox_sync_message_limit,
            manual_item_limit=settings.inbox_initial_item_limit,
            lease_seconds=sync_lease_seconds,
        ),
        drafts=InboxDraftDeliveryService(
            unit_of_work=SqlAlchemyInboxDraftUnitOfWorkFactory(database),
            gateways=registry,
            access=access,
        ),
        close=registry.close,
    )


def _gateway_registry(
    settings: Settings,
) -> tuple[InboxGatewayRegistry, str, str, str]:
    if settings.gmail_adapter_enabled:
        client_id = settings.google_oauth_client_id or ""
        client_secret = settings.google_oauth_secret_value() or ""
        redirect_uri = settings.google_oauth_redirect_uri or ""
        authorization = GmailAuthorizationAdapter(
            client_id=client_id,
            client_secret=client_secret,
            timeout_seconds=settings.inbox_provider_timeout_seconds,
        )
        reader = GmailReadAdapter(timeout_seconds=settings.inbox_provider_timeout_seconds)
        drafts = (
            GmailDraftAdapter(timeout_seconds=settings.inbox_provider_timeout_seconds)
            if settings.inbox_draft_writeback_enabled
            else None
        )
        adapter = InboxAdapter(
            adapter_key="gmail_v1",
            authorization=authorization,
            reader=reader,
            drafts=drafts,
            close=lambda: _close_gateways(authorization, reader, drafts),
        )
        return InboxGatewayRegistry((adapter,)), "gmail_v1", client_id, redirect_uri
    deterministic = DeterministicInboxGateway()
    adapter = InboxAdapter(
        adapter_key=deterministic.adapter_key,
        authorization=deterministic,
        reader=deterministic,
        drafts=deterministic if settings.inbox_draft_writeback_enabled else None,
        close=deterministic.close,
    )
    return (
        InboxGatewayRegistry((adapter,)),
        deterministic.adapter_key,
        "deterministic-client",
        "/connections/inbox/callback",
    )


def _scopes(settings: Settings) -> dict[InboxCapability, str]:
    if settings.gmail_adapter_enabled:
        return {
            InboxCapability.READ_CONVERSATIONS: GMAIL_READ_SCOPE,
            InboxCapability.CREATE_DRAFTS: GMAIL_DRAFT_SCOPE,
        }
    return {
        InboxCapability.READ_CONVERSATIONS: InboxCapability.READ_CONVERSATIONS.value,
        InboxCapability.CREATE_DRAFTS: InboxCapability.CREATE_DRAFTS.value,
    }


def _vault_key(settings: Settings) -> bytes:
    configured = settings.credential_vault_key_bytes()
    if configured is not None:
        return configured
    return sha256(b"case-resolution-copilot-deterministic-inbox-v1").digest()


def _close_gateways(*gateways: object | None) -> None:
    for gateway in gateways:
        close = getattr(gateway, "close", None)
        if callable(close):
            close()
