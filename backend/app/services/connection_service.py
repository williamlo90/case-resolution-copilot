from typing import Protocol

from app.domain.connections import (
    ConnectionHealth,
    ConnectionHealthCheckRecord,
    ConnectionNotFound,
    ConnectionPageRecord,
    ConnectionRecord,
    ConnectionVersionConflict,
)
from app.domain.identity import ActorContext, Permission
from app.integrations.action_gateway import ActionGateway
from app.persistence.connection_repository import ConnectionRepository
from app.persistence.database import Database
from app.security.authorization import require_permission


class ConnectionQueryStore(Protocol):
    def get(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> ConnectionRecord | None: ...

    def list(
        self,
        *,
        organization_public_id: str,
        health: str | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ConnectionPageRecord: ...


class ConnectionQueryService:
    def __init__(self, store: ConnectionQueryStore) -> None:
        self._store = store

    def get(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
    ) -> ConnectionRecord:
        require_permission(actor, Permission.CONNECTION_READ)
        connection = self._store.get(
            organization_public_id=actor.organization_id,
            connection_public_id=connection_id,
        )
        if connection is None:
            raise ConnectionNotFound("The connection was not found.")
        return connection

    def list(
        self,
        *,
        actor: ActorContext,
        health: str | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ConnectionPageRecord:
        require_permission(actor, Permission.CONNECTION_READ)
        return self._store.list(
            organization_public_id=actor.organization_id,
            health=health,
            query=query,
            cursor=cursor,
            limit=limit,
        )


class ConnectionCommandService:
    def __init__(self, database: Database, gateway: ActionGateway) -> None:
        self._database = database
        self._gateway = gateway

    def test(
        self,
        *,
        actor: ActorContext,
        connection_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> tuple[ConnectionRecord, ConnectionHealthCheckRecord]:
        require_permission(actor, Permission.CONNECTION_MANAGE)
        with self._database.session() as session:
            current = ConnectionRepository(session).get(
                organization_public_id=actor.organization_id,
                connection_public_id=connection_id,
            )
            if current is None:
                raise ConnectionNotFound("The connection was not found.")
            if current.version != expected_version:
                raise ConnectionVersionConflict(
                    expected_version=expected_version,
                    current_version=current.version,
                )

        try:
            health, detail = self._gateway.check_health(
                adapter_key=current.adapter_key,
                provider_type=current.provider_type,
            )
        except Exception:
            health = ConnectionHealth.UNAVAILABLE
            detail = "The connection check did not complete. Try again after checking the target."
        with self._database.session() as session:
            return ConnectionRepository(session).record_health_check(
                organization_public_id=actor.organization_id,
                connection_public_id=connection_id,
                actor_id=actor.actor_id,
                expected_version=expected_version,
                health=health,
                detail=detail,
                correlation_id=correlation_id,
            )
