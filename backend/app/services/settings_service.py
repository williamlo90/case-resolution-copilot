from typing import Protocol

from app.domain.identity import ActorContext, Permission
from app.domain.settings import (
    OrganizationSettingsRecord,
    SettingsNotFound,
    SettingsSection,
    SettingsUpdateReceipt,
    SettingsValues,
)
from app.security.authorization import require_permission


class OrganizationSettingsStore(Protocol):
    def get(
        self,
        *,
        organization_public_id: str,
        section: SettingsSection,
    ) -> OrganizationSettingsRecord | None: ...

    def update(
        self,
        *,
        organization_public_id: str,
        actor_id: str,
        section: SettingsSection,
        expected_version: int,
        configuration: SettingsValues,
        correlation_id: str,
    ) -> SettingsUpdateReceipt: ...


class SettingsService:
    def __init__(self, store: OrganizationSettingsStore) -> None:
        self._store = store

    def get(
        self,
        *,
        actor: ActorContext,
        section: SettingsSection,
    ) -> OrganizationSettingsRecord:
        require_permission(actor, Permission.SETTINGS_MANAGE)
        record = self._store.get(
            organization_public_id=actor.organization_id,
            section=section,
        )
        if record is None:
            raise SettingsNotFound("The organization settings were not found.")
        return record

    def update(
        self,
        *,
        actor: ActorContext,
        section: SettingsSection,
        expected_version: int,
        configuration: SettingsValues,
        correlation_id: str,
    ) -> SettingsUpdateReceipt:
        require_permission(actor, Permission.SETTINGS_MANAGE)
        return self._store.update(
            organization_public_id=actor.organization_id,
            actor_id=actor.actor_id,
            section=section,
            expected_version=expected_version,
            configuration=configuration,
            correlation_id=correlation_id,
        )
