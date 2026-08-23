from datetime import UTC, datetime

import pytest

from app.domain.connections import ConnectionHealth, CredentialStatus
from app.domain.inbox import (
    InboxConnectionStatusRecord,
    InboxImportMode,
    InboxNotFound,
    InboxSyncStatus,
)
from app.security.authentication import DeterministicAuthProvider
from app.security.authorization import PermissionDenied
from app.services.inbox.status import InboxStatusService

NOW = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)


class _StatusStore:
    def __init__(self, result: InboxConnectionStatusRecord | None) -> None:
        self.result = result
        self.requested_scope: tuple[str, str] | None = None

    def get(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> InboxConnectionStatusRecord | None:
        self.requested_scope = (organization_public_id, connection_public_id)
        return self.result


def _status() -> InboxConnectionStatusRecord:
    return InboxConnectionStatusRecord(
        connection_public_id="CON-INBOX-0001",
        account_address="operator@example.test",
        import_mode=InboxImportMode.MANUAL,
        health=ConnectionHealth.HEALTHY,
        credential_status=CredentialStatus.CONNECTED,
        sync_status=InboxSyncStatus.CURRENT,
        capabilities=("read_messages",),
        last_checked_at=NOW,
        last_successful_sync_at=NOW,
        last_error_code=None,
    )


def test_inbox_status_read_is_scoped_to_the_actor_tenant() -> None:
    actor = DeterministicAuthProvider().authenticate("USR-0003")
    store = _StatusStore(_status())

    result = InboxStatusService(store).get(
        actor=actor,
        connection_id="CON-INBOX-0001",
    )

    assert result == _status()
    assert store.requested_scope == (actor.organization_id, "CON-INBOX-0001")


def test_inbox_status_fails_closed_for_missing_or_unauthorized_reads() -> None:
    actor = DeterministicAuthProvider().authenticate("USR-0003")
    with pytest.raises(InboxNotFound):
        InboxStatusService(_StatusStore(None)).get(
            actor=actor,
            connection_id="CON-MISSING",
        )

    unauthorized = actor.model_copy(update={"permissions": frozenset()})
    with pytest.raises(PermissionDenied):
        InboxStatusService(_StatusStore(_status())).get(
            actor=unauthorized,
            connection_id="CON-INBOX-0001",
        )
