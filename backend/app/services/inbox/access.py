from pydantic import SecretStr

from app.domain.inbox import (
    InboxAccessContext,
    RefreshCredential,
)
from app.ports.credentials import CredentialProtector
from app.ports.inbox import InboxAccessGatewayResolver
from app.ports.inbox_authorization_persistence import (
    InboxAuthorizationUnitOfWorkFactory,
)


class InboxAccessService:
    def __init__(
        self,
        *,
        unit_of_work: InboxAuthorizationUnitOfWorkFactory,
        gateways: InboxAccessGatewayResolver,
        credentials: CredentialProtector,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._gateways = gateways
        self._credentials = credentials

    def access(
        self,
        *,
        organization_id: str,
        connection_id: str,
    ) -> InboxAccessContext:
        with self._unit_of_work() as uow:
            stored = uow.credentials.get(
                organization_public_id=organization_id,
                connection_public_id=connection_id,
            )
        gateway = self._gateways.authorization(stored.adapter_key)
        refresh_token = self._credentials.decrypt(
            envelope=stored.credential,
            organization_id=organization_id,
            connection_id=stored.connection_public_id,
            provider=stored.provider,
        )
        access = gateway.refresh_access(
            RefreshCredential(refresh_token=SecretStr(refresh_token))
        )
        return InboxAccessContext(
            organization_id=stored.organization_id,
            connection_id=stored.connection_id,
            connection_public_id=stored.connection_public_id,
            adapter_key=stored.adapter_key,
            account_address=stored.account_address,
            import_mode=stored.import_mode,
            access=access,
        )
