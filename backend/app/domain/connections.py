from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConnectionEnvironment(StrEnum):
    DEMO = "demo"
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class ConnectionHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


class CredentialStatus(StrEnum):
    DEMO = "demo"
    CONNECTED = "connected"
    MISSING = "missing"
    EXPIRED = "expired"


class ConnectionSeed(BaseModel):
    public_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    provider_type: str = Field(min_length=1, max_length=100)
    adapter_key: str = Field(min_length=1, max_length=100)
    environment: ConnectionEnvironment
    health: ConnectionHealth
    credential_status: CredentialStatus
    read_capabilities: list[str]
    write_capabilities: list[str]
    action_types: list[str]
    affected_work: list[str]
    last_checked_at: datetime | None = None
    runtime_config_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )


class ConnectionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    name: str
    provider_type: str
    adapter_key: str
    environment: ConnectionEnvironment
    health: ConnectionHealth
    last_checked_at: datetime | None
    credential_status: CredentialStatus
    read_capabilities: list[str]
    write_capabilities: list[str]
    action_types: list[str]
    affected_work: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class ConnectionHealthCheckRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    connection_id: UUID
    health: ConnectionHealth
    detail: str
    checked_by_id: UUID
    checked_by_public_id: str
    checked_by_name: str
    checked_at: datetime


class ConnectionPageRecord(BaseModel):
    items: list[ConnectionRecord]
    next_cursor: str | None
    total: int


class ConnectionNotFound(LookupError):
    pass


class ConnectionConflict(RuntimeError):
    pass


class InvalidConnectionCursor(ValueError):
    pass


class ConnectionVersionConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The connection changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version
