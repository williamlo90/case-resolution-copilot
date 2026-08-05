from typing import Protocol

from app.domain.identity import ActorContext, Permission
from app.domain.notifications import NotificationPageRecord, NotificationRecord
from app.security.authorization import require_permission


class NotificationStore(Protocol):
    def list_for_actor(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        unread_only: bool,
        cursor: str | None,
        limit: int,
    ) -> NotificationPageRecord: ...

    def mark_read(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        notification_public_id: str,
        expected_version: int,
    ) -> NotificationRecord: ...

    def mark_all_read(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
    ) -> int: ...


class NotificationService:
    def __init__(self, store: NotificationStore) -> None:
        self._store = store

    def list(
        self,
        *,
        actor: ActorContext,
        unread_only: bool,
        cursor: str | None,
        limit: int,
    ) -> NotificationPageRecord:
        require_permission(actor, Permission.SESSION_READ)
        return self._store.list_for_actor(
            organization_public_id=actor.organization_id,
            actor_id=actor.actor_id,
            unread_only=unread_only,
            cursor=cursor,
            limit=limit,
        )

    def mark_read(
        self,
        *,
        actor: ActorContext,
        notification_id: str,
        expected_version: int,
    ) -> NotificationRecord:
        require_permission(actor, Permission.SESSION_READ)
        return self._store.mark_read(
            organization_public_id=actor.organization_id,
            actor_id=actor.actor_id,
            notification_public_id=notification_id,
            expected_version=expected_version,
        )

    def mark_all_read(self, *, actor: ActorContext) -> int:
        require_permission(actor, Permission.SESSION_READ)
        return self._store.mark_all_read(
            organization_public_id=actor.organization_id,
            actor_id=actor.actor_id,
        )
