from typing import Protocol

from app.domain.inbox import InboxConnectionStatusRecord


class InboxStatusStore(Protocol):
    def get(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> InboxConnectionStatusRecord | None: ...
