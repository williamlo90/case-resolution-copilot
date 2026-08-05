from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import cast

import pytest

from app.config import Settings
from app.domain.connections import ConnectionSeed
from app.integrations import connection_activation
from app.persistence.database import Database


class FakeDatabase:
    @contextmanager
    def session(self) -> Iterator[object]:
        yield object()


class FakeConnectionRepository:
    last_instance: "FakeConnectionRepository | None" = None

    def __init__(self, _session: object) -> None:
        self.locked = False
        self.synchronized: list[ConnectionSeed] = []
        self.deactivation: tuple[str | None, set[str]] | None = None
        FakeConnectionRepository.last_instance = self

    def lock_runtime_configuration(self) -> None:
        self.locked = True

    def synchronize_runtime(
        self,
        *,
        organization_public_id: str,
        command: ConnectionSeed,
        correlation_id: str,
    ) -> SimpleNamespace:
        del organization_public_id, correlation_id
        self.synchronized.append(command)
        return SimpleNamespace(public_id=command.public_id)

    def deactivate_runtime(
        self,
        *,
        active_organization_public_id: str | None,
        active_connection_ids: set[str],
        correlation_id: str,
    ) -> list[str]:
        del correlation_id
        self.deactivation = (
            active_organization_public_id,
            active_connection_ids,
        )
        return []


def test_disabled_providers_deactivate_stale_runtime_connections_when_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        connection_activation,
        "ConnectionRepository",
        FakeConnectionRepository,
    )

    activated = connection_activation.activate_runtime_connections(
        database=cast(Database, FakeDatabase()),
        settings=Settings(
            integration_organization_id="ORG-0001",
            _env_file=None,
        ),
    )

    repository = FakeConnectionRepository.last_instance
    assert repository is not None
    assert activated == []
    assert repository.locked
    assert repository.synchronized == []
    assert repository.deactivation == ("ORG-0001", set())


def test_runtime_activation_carries_a_non_secret_configuration_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        connection_activation,
        "ConnectionRepository",
        FakeConnectionRepository,
    )
    settings = Settings(
        action_target_provider="signed_webhook",
        integration_organization_id="ORG-0001",
        action_webhook_url="https://actions.example.com/hooks",
        action_webhook_secret="action-secret-with-at-least-32-characters",
        _env_file=None,
    )

    activated = connection_activation.activate_runtime_connections(
        database=cast(Database, FakeDatabase()),
        settings=settings,
    )

    repository = FakeConnectionRepository.last_instance
    assert repository is not None
    assert activated == ["CN-WEBHOOK-ACTIONS"]
    assert len(repository.synchronized) == 1
    fingerprint = repository.synchronized[0].runtime_config_fingerprint
    assert fingerprint is not None and len(fingerprint) == 64
    assert "action-secret" not in fingerprint
    assert repository.deactivation == (
        "ORG-0001",
        {"CN-WEBHOOK-ACTIONS"},
    )
