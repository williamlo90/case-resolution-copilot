from pydantic import Field

from app.api.schemas.common import (
    ActorSummaryResponse,
    ApiSchema,
    CursorPage,
    DataResponse,
    PublicId,
    UtcDateTime,
    Version,
)
from app.domain.connections import (
    ConnectionEnvironment,
    ConnectionHealth,
    CredentialStatus,
)


class ConnectionCapabilitiesResponse(ApiSchema):
    read: list[str]
    write: list[str]


class ConnectionResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    name: str = Field(min_length=1, max_length=200)
    provider_type: str = Field(min_length=1, max_length=100)
    environment: ConnectionEnvironment
    health: ConnectionHealth
    last_checked_at: UtcDateTime | None
    credential_status: CredentialStatus
    capabilities: ConnectionCapabilitiesResponse
    affected_work: list[str]
    version: Version


class ConnectionHealthReceiptResponse(ApiSchema):
    id: PublicId
    connection_id: PublicId
    health: ConnectionHealth
    detail: str = Field(min_length=1, max_length=1000)
    checked_at: UtcDateTime
    checked_by: ActorSummaryResponse


class ConnectionHealthResultResponse(ApiSchema):
    connection: ConnectionResponse
    receipt: ConnectionHealthReceiptResponse


class TestConnectionRequest(ApiSchema):
    expected_version: Version


class ConnectionDetailEnvelope(DataResponse[ConnectionResponse]):
    pass


class ConnectionHealthEnvelope(DataResponse[ConnectionHealthResultResponse]):
    pass


class ConnectionListResponse(CursorPage[ConnectionResponse]):
    pass
