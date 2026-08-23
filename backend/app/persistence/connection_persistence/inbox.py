from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.connections import ConnectionRecord
from app.domain.inbox import InboxConflict, InboxNotFound
from app.persistence.models import (
    ConnectionModel,
    InboxConnectionProfileModel,
    OrganizationModel,
    utc_now,
)


class InboxConnectionWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def connect(
        self,
        *,
        organization_id: UUID,
        account_address: str,
        provider_account_id: str,
        adapter_key: str,
        read_capabilities: list[str],
        write_capabilities: list[str],
    ) -> ConnectionRecord:
        connection = self._session.scalar(
            select(ConnectionModel)
            .where(
                ConnectionModel.organization_id == organization_id,
                ConnectionModel.provider_type == "inbox",
            )
            .with_for_update()
        )
        now = utc_now()
        if connection is None:
            connection = ConnectionModel(
                id=uuid4(),
                public_id=f"CON-INBOX-{uuid4().hex[:10].upper()}",
                organization_id=organization_id,
                name=f"Inbox - {account_address}"[:200],
                provider_type="inbox",
                adapter_key=adapter_key,
                environment="sandbox",
                health="healthy",
                last_checked_at=now,
                credential_status="connected",
                read_capabilities=read_capabilities,
                write_capabilities=write_capabilities,
                action_types=[],
                affected_work=["case_import", "response_draft"],
                runtime_config_fingerprint=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            self._session.add(connection)
        else:
            profile = self._session.scalar(
                select(InboxConnectionProfileModel)
                .where(
                    InboxConnectionProfileModel.organization_id == organization_id,
                    InboxConnectionProfileModel.connection_id == connection.id,
                )
                .with_for_update()
            )
            if profile is not None and (
                profile.provider_account_id != provider_account_id
                or profile.account_address.casefold() != account_address.casefold()
            ):
                raise InboxConflict(
                    "This connection already belongs to a different inbox account. "
                    "Reconnect the original account so its imported history stays trustworthy."
                )
            connection.name = f"Inbox - {account_address}"[:200]
            connection.adapter_key = adapter_key
            connection.health = "healthy"
            connection.last_checked_at = now
            connection.credential_status = "connected"
            connection.read_capabilities = read_capabilities
            connection.write_capabilities = write_capabilities
            connection.version += 1
            connection.updated_at = now
        self._session.flush()
        return ConnectionRecord.model_validate(connection)

    def disconnect(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> ConnectionRecord:
        connection = self._session.scalar(
            select(ConnectionModel)
            .join(OrganizationModel, OrganizationModel.id == ConnectionModel.organization_id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                ConnectionModel.public_id == connection_public_id,
                ConnectionModel.provider_type == "inbox",
            )
            .with_for_update()
        )
        if connection is None:
            raise InboxNotFound("The inbox connection was not found.")
        connection.health = "not_configured"
        connection.credential_status = "missing"
        connection.read_capabilities = []
        connection.write_capabilities = []
        connection.version += 1
        connection.updated_at = utc_now()
        self._session.flush()
        return ConnectionRecord.model_validate(connection)
