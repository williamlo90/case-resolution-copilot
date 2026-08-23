from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.connections import ConnectionHealth, CredentialStatus

from .sync import InboxImportMode, InboxSyncStatus


class InboxConnectionStatusRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    connection_public_id: str
    account_address: str
    import_mode: InboxImportMode
    health: ConnectionHealth
    credential_status: CredentialStatus
    sync_status: InboxSyncStatus
    capabilities: tuple[str, ...]
    last_checked_at: datetime | None
    last_successful_sync_at: datetime | None
    last_error_code: str | None
