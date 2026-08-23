from typing import Protocol

from app.domain.inbox import InboxAccessContext


class InboxAccessProvider(Protocol):
    def access(
        self,
        *,
        organization_id: str,
        connection_id: str,
    ) -> InboxAccessContext: ...
