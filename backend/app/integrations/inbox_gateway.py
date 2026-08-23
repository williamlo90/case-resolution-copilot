from collections.abc import Callable
from dataclasses import dataclass

from app.ports.inbox import (
    InboxAuthorizationGateway,
    InboxDraftGateway,
    InboxReadGateway,
)


@dataclass(frozen=True, slots=True)
class InboxAdapter:
    adapter_key: str
    authorization: InboxAuthorizationGateway
    reader: InboxReadGateway
    drafts: InboxDraftGateway | None
    close: Callable[[], None]


class InboxGatewayRegistry:
    def __init__(self, adapters: tuple[InboxAdapter, ...]) -> None:
        self._adapters = {adapter.adapter_key: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("Inbox adapter keys must be unique.")

    def authorization(self, adapter_key: str) -> InboxAuthorizationGateway:
        return self._required(adapter_key).authorization

    def reader(self, adapter_key: str) -> InboxReadGateway:
        return self._required(adapter_key).reader

    def drafts(self, adapter_key: str) -> InboxDraftGateway:
        gateway = self._required(adapter_key).drafts
        if gateway is None:
            raise LookupError(f"Inbox adapter {adapter_key!r} cannot create drafts.")
        return gateway

    def close(self) -> None:
        for adapter in self._adapters.values():
            adapter.close()

    def _required(self, adapter_key: str) -> InboxAdapter:
        try:
            return self._adapters[adapter_key]
        except KeyError as exc:
            raise LookupError(f"Inbox adapter {adapter_key!r} is not registered.") from exc
