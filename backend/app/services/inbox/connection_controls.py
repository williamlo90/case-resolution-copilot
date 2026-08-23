from pydantic import SecretStr

from app.domain.identity import ActorContext, Permission
from app.domain.inbox import (
    InboxAuthorizationError,
    InboxDisconnectResult,
    InboxImportMode,
    InboxProviderUnavailable,
    RefreshCredential,
)
from app.ports.credentials import CredentialProtector
from app.ports.inbox import InboxAuthorizationGatewayResolver
from app.ports.inbox_authorization_persistence import (
    InboxAuthorizationUnitOfWorkFactory,
)
from app.security.authorization import require_permission

from .access import InboxAccessService


class InboxConnectionControlService:
    def __init__(
        self,
        *,
        unit_of_work: InboxAuthorizationUnitOfWorkFactory,
        gateways: InboxAuthorizationGatewayResolver,
        credentials: CredentialProtector,
        access: InboxAccessService,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._gateways = gateways
        self._credentials = credentials
        self._access = access

    def pause(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
        correlation_id: str,
    ) -> None:
        require_permission(actor, Permission.CONNECTION_MANAGE)
        with self._unit_of_work() as uow:
            uow.credentials.set_import_mode(
                organization_public_id=actor.organization_id,
                connection_public_id=connection_id,
                mode=InboxImportMode.PAUSED,
                actor_id=actor.actor_id,
                correlation_id=correlation_id,
            )

    def resume(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
        correlation_id: str,
    ) -> None:
        require_permission(actor, Permission.CONNECTION_MANAGE)
        access = self._access.access(
            organization_id=actor.organization_id,
            connection_id=connection_id,
        )
        account = self._gateways.reader(access.adapter_key).get_account(access.access)
        if account.address.casefold() != access.account_address.casefold():
            raise InboxAuthorizationError(
                "The signed-in inbox does not match the connected account."
            )
        with self._unit_of_work() as uow:
            uow.credentials.set_import_mode(
                organization_public_id=actor.organization_id,
                connection_public_id=connection_id,
                mode=InboxImportMode.MANUAL,
                actor_id=actor.actor_id,
                correlation_id=correlation_id,
            )

    def disconnect(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
        correlation_id: str,
    ) -> InboxDisconnectResult:
        require_permission(actor, Permission.CONNECTION_MANAGE)
        with self._unit_of_work() as uow:
            stored = uow.credentials.get(
                organization_public_id=actor.organization_id,
                connection_public_id=connection_id,
            )
        gateway = self._gateways.authorization(stored.adapter_key)
        refresh_token = self._credentials.decrypt(
            envelope=stored.credential,
            organization_id=actor.organization_id,
            connection_id=stored.connection_public_id,
            provider=stored.provider,
        )
        provider_revoked = False
        try:
            provider_revoked = gateway.revoke(
                RefreshCredential(refresh_token=SecretStr(refresh_token))
            ).revoked
        except (InboxAuthorizationError, InboxProviderUnavailable):
            provider_revoked = False
        with self._unit_of_work() as uow:
            uow.credentials.delete_credential(
                organization_public_id=actor.organization_id,
                connection_public_id=connection_id,
                actor_id=actor.actor_id,
                correlation_id=correlation_id,
            )
            connection = uow.connections.disconnect(
                organization_public_id=actor.organization_id,
                connection_public_id=connection_id,
            )
        return InboxDisconnectResult(
            connection_public_id=connection.public_id,
            provider_revoked=provider_revoked,
        )
