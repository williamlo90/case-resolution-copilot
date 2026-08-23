from datetime import UTC, datetime, timedelta

from app.domain.identity import ActorContext, Permission
from app.domain.inbox import InboxConflict, InboxImportMode, ThreadPage
from app.ports.inbox import InboxReadGatewayResolver
from app.ports.inbox_access import InboxAccessProvider
from app.security.authorization import require_permission


class InboxBrowseService:
    def __init__(
        self,
        *,
        gateways: InboxReadGatewayResolver,
        access: InboxAccessProvider,
        window_days: int,
        item_limit: int,
    ) -> None:
        self._gateways = gateways
        self._access = access
        self._window_days = window_days
        self._item_limit = item_limit

    def list_threads(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
        page_token: str | None,
        limit: int,
    ) -> ThreadPage:
        require_permission(actor, Permission.CONNECTION_READ)
        access = self._access.access(
            organization_id=actor.organization_id,
            connection_id=connection_id,
        )
        if access.import_mode == InboxImportMode.PAUSED.value:
            raise InboxConflict("Inbox import is paused.")
        bounded_limit = min(limit, self._item_limit)
        return self._gateways.reader(access.adapter_key).list_threads(
            access=access.access,
            label_filter=("INBOX",),
            after=datetime.now(UTC) - timedelta(days=self._window_days),
            page_token=page_token,
            limit=bounded_limit,
        )
