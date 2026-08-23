from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.domain.inbox import InboxConnectionStatusRecord, InboxSyncStatus
from app.persistence.models import (
    ConnectionModel,
    InboxConnectionProfileModel,
    InboxSyncCheckpointModel,
    OrganizationModel,
)


class InboxStatusRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> InboxConnectionStatusRecord | None:
        row = self._session.execute(
            select(
                ConnectionModel,
                InboxConnectionProfileModel,
                InboxSyncCheckpointModel,
            )
            .join(
                OrganizationModel,
                OrganizationModel.id == ConnectionModel.organization_id,
            )
            .join(
                InboxConnectionProfileModel,
                and_(
                    InboxConnectionProfileModel.organization_id
                    == ConnectionModel.organization_id,
                    InboxConnectionProfileModel.connection_id == ConnectionModel.id,
                ),
            )
            .outerjoin(
                InboxSyncCheckpointModel,
                and_(
                    InboxSyncCheckpointModel.organization_id
                    == ConnectionModel.organization_id,
                    InboxSyncCheckpointModel.connection_id == ConnectionModel.id,
                ),
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                ConnectionModel.public_id == connection_public_id,
                ConnectionModel.provider_type == "inbox",
            )
        ).one_or_none()
        if row is None:
            return None
        connection, profile, checkpoint = row
        return InboxConnectionStatusRecord(
            connection_public_id=connection.public_id,
            account_address=profile.account_address,
            import_mode=profile.import_mode,
            health=connection.health,
            credential_status=connection.credential_status,
            sync_status=(
                checkpoint.status if checkpoint is not None else InboxSyncStatus.DELAYED
            ),
            capabilities=tuple(
                dict.fromkeys(
                    [*connection.read_capabilities, *connection.write_capabilities]
                )
            ),
            last_checked_at=connection.last_checked_at,
            last_successful_sync_at=(
                checkpoint.last_successful_sync_at
                if checkpoint is not None
                else profile.last_successful_sync_at
            ),
            last_error_code=(
                checkpoint.last_error_code
                if checkpoint is not None
                else "sync_checkpoint_missing"
            ),
        )
