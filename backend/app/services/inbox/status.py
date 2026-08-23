from app.domain.identity import ActorContext, Permission
from app.domain.inbox import InboxConnectionStatusRecord, InboxNotFound
from app.ports.inbox_status import InboxStatusStore
from app.security.authorization import require_permission


class InboxStatusService:
    def __init__(self, store: InboxStatusStore) -> None:
        self._store = store

    def get(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
    ) -> InboxConnectionStatusRecord:
        require_permission(actor, Permission.CONNECTION_READ)
        status = self._store.get(
            organization_public_id=actor.organization_id,
            connection_public_id=connection_id,
        )
        if status is None:
            raise InboxNotFound("The inbox connection was not found.")
        return status
