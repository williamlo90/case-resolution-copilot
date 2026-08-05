from app.api.schemas.common import ActorSummaryResponse
from app.api.schemas.connections import (
    ConnectionCapabilitiesResponse,
    ConnectionHealthReceiptResponse,
    ConnectionHealthResultResponse,
    ConnectionResponse,
)
from app.domain.connections import ConnectionHealthCheckRecord, ConnectionRecord


def present_connection(
    connection: ConnectionRecord,
    *,
    organization_id: str,
) -> ConnectionResponse:
    return ConnectionResponse(
        id=connection.public_id,
        organization_id=organization_id,
        name=connection.name,
        provider_type=connection.provider_type,
        environment=connection.environment,
        health=connection.health,
        last_checked_at=connection.last_checked_at,
        credential_status=connection.credential_status,
        capabilities=ConnectionCapabilitiesResponse(
            read=connection.read_capabilities,
            write=connection.write_capabilities,
        ),
        affected_work=connection.affected_work,
        version=connection.version,
    )


def present_health_result(
    connection: ConnectionRecord,
    receipt: ConnectionHealthCheckRecord,
    *,
    organization_id: str,
) -> ConnectionHealthResultResponse:
    return ConnectionHealthResultResponse(
        connection=present_connection(
            connection,
            organization_id=organization_id,
        ),
        receipt=ConnectionHealthReceiptResponse(
            id=receipt.public_id,
            connection_id=connection.public_id,
            health=receipt.health,
            detail=receipt.detail,
            checked_at=receipt.checked_at,
            checked_by=ActorSummaryResponse(
                id=receipt.checked_by_public_id,
                name=receipt.checked_by_name,
            ),
        ),
    )
