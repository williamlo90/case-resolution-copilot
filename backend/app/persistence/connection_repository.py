import base64
import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.domain.connections import (
    ConnectionConflict,
    ConnectionHealth,
    ConnectionHealthCheckRecord,
    ConnectionNotFound,
    ConnectionPageRecord,
    ConnectionRecord,
    ConnectionSeed,
    ConnectionVersionConflict,
    InvalidConnectionCursor,
)
from app.domain.identity import ActorMembershipNotFound
from app.persistence.models import (
    AuditEventModel,
    ConnectionHealthCheckModel,
    ConnectionModel,
    MembershipModel,
    OrganizationModel,
    utc_now,
)

_PROVIDER_BY_ACTION = {
    "reverse_duplicate_charge": "billing",
    "issue_refund": "billing",
    "start_verified_recovery": "identity",
    "apply_service_correction": "service_operations",
}

_PROVIDER_LABEL = {
    "billing": "Billing operations",
    "identity": "Identity operations",
    "service_operations": "Service operations",
}

_HEALTH_ORDER = {
    ConnectionHealth.HEALTHY.value: 0,
    ConnectionHealth.DEGRADED.value: 1,
    ConnectionHealth.UNAVAILABLE.value: 2,
    ConnectionHealth.NOT_CONFIGURED.value: 3,
}

_ENVIRONMENT_ORDER = {
    "production": 0,
    "sandbox": 1,
    "demo": 2,
}


class ConnectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def seed(
        self,
        *,
        organization_public_id: str,
        command: ConnectionSeed,
        correlation_id: str,
    ) -> ConnectionRecord:
        organization = self._organization(organization_public_id)
        if organization is None:
            raise ConnectionNotFound("The organization was not found.")
        existing = self._session.scalar(
            select(ConnectionModel).where(
                ConnectionModel.organization_id == organization.id,
                or_(
                    ConnectionModel.public_id == command.public_id,
                    ConnectionModel.name == command.name,
                ),
            )
        )
        if existing is not None:
            if existing.public_id != command.public_id or existing.name != command.name:
                raise ConnectionConflict(
                    "A connection already uses this identifier or display name."
                )
            return ConnectionRecord.model_validate(existing)

        now = utc_now()
        connection = ConnectionModel(
            public_id=command.public_id,
            organization_id=organization.id,
            name=command.name,
            provider_type=command.provider_type,
            adapter_key=command.adapter_key,
            environment=command.environment.value,
            health=command.health.value,
            last_checked_at=command.last_checked_at,
            credential_status=command.credential_status.value,
            read_capabilities=list(command.read_capabilities),
            write_capabilities=list(command.write_capabilities),
            action_types=list(command.action_types),
            affected_work=list(command.affected_work),
            runtime_config_fingerprint=command.runtime_config_fingerprint,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._session.add(connection)
        self._session.add(
            AuditEventModel(
                organization_id=organization.id,
                task_id=None,
                run_id=None,
                event_type="connection.seeded",
                actor_type="system",
                actor_id="connection-seed",
                subject_type="connection",
                subject_id=command.public_id,
                summary="A connection definition was added.",
                data={
                    "provider_type": command.provider_type,
                    "environment": command.environment.value,
                    "health": command.health.value,
                },
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )
        self._session.flush()
        return ConnectionRecord.model_validate(connection)

    def synchronize_runtime(
        self,
        *,
        organization_public_id: str,
        command: ConnectionSeed,
        correlation_id: str,
    ) -> ConnectionRecord:
        organization = self._organization(organization_public_id)
        if organization is None:
            raise ConnectionNotFound("The organization was not found.")
        existing = self._session.scalar(
            select(ConnectionModel).where(
                ConnectionModel.organization_id == organization.id,
                or_(
                    ConnectionModel.public_id == command.public_id,
                    ConnectionModel.name == command.name,
                ),
            )
        )
        if existing is None:
            return self.seed(
                organization_public_id=organization_public_id,
                command=command,
                correlation_id=correlation_id,
            )
        if existing.public_id != command.public_id or existing.name != command.name:
            raise ConnectionConflict(
                "A connection already uses this identifier or display name."
            )

        activating = (
            existing.adapter_key != command.adapter_key
            or existing.credential_status != command.credential_status.value
            or existing.runtime_config_fingerprint
            != command.runtime_config_fingerprint
        )
        values: dict[str, object] = {
            "provider_type": command.provider_type,
            "adapter_key": command.adapter_key,
            "environment": command.environment.value,
            "credential_status": command.credential_status.value,
            "read_capabilities": list(command.read_capabilities),
            "write_capabilities": list(command.write_capabilities),
            "action_types": list(command.action_types),
            "affected_work": list(command.affected_work),
            "runtime_config_fingerprint": command.runtime_config_fingerprint,
        }
        if not command.action_types or activating:
            values["health"] = command.health.value
            values["last_checked_at"] = command.last_checked_at
        changed = any(getattr(existing, field) != value for field, value in values.items())
        if changed:
            for field, value in values.items():
                setattr(existing, field, value)
            existing.version += 1
            existing.updated_at = utc_now()
            self._session.add(
                AuditEventModel(
                    organization_id=organization.id,
                    task_id=None,
                    run_id=None,
                    event_type="connection.runtime_synchronized",
                    actor_type="system",
                    actor_id="connection-activation",
                    subject_type="connection",
                    subject_id=command.public_id,
                    summary="Runtime connection settings were synchronized.",
                    data={
                        "provider_type": command.provider_type,
                        "environment": command.environment.value,
                    },
                    correlation_id=correlation_id,
                )
            )
            self._session.flush()
        return ConnectionRecord.model_validate(existing)

    def lock_runtime_configuration(self) -> None:
        lock_key = int.from_bytes(
            sha256(b"runtime-connections:global").digest()[:8],
            byteorder="big",
            signed=True,
        )
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )

    def deactivate_runtime(
        self,
        *,
        active_organization_public_id: str | None,
        active_connection_ids: set[str],
        correlation_id: str,
    ) -> list[str]:
        active_organization = (
            self._organization(active_organization_public_id)
            if active_organization_public_id is not None
            else None
        )
        if active_connection_ids and active_organization is None:
            raise ConnectionNotFound("The organization was not found.")
        runtime_ids = {"CN-WEBHOOK-INTAKE", "CN-WEBHOOK-ACTIONS"}
        connections = list(
            self._session.scalars(
                select(ConnectionModel).where(
                    ConnectionModel.public_id.in_(runtime_ids),
                ).with_for_update()
            )
        )
        changed_ids: list[str] = []
        now = utc_now()
        for connection in connections:
            if (
                active_organization is not None
                and connection.organization_id == active_organization.id
                and connection.public_id in active_connection_ids
            ):
                continue
            if (
                connection.health == ConnectionHealth.NOT_CONFIGURED.value
                and connection.credential_status == "missing"
                and connection.runtime_config_fingerprint is None
            ):
                continue
            connection.health = ConnectionHealth.NOT_CONFIGURED.value
            connection.credential_status = "missing"
            connection.last_checked_at = None
            connection.runtime_config_fingerprint = None
            connection.version += 1
            connection.updated_at = now
            changed_ids.append(connection.public_id)
            self._session.add(
                AuditEventModel(
                    organization_id=connection.organization_id,
                    task_id=None,
                    run_id=None,
                    event_type="connection.runtime_deactivated",
                    actor_type="system",
                    actor_id="connection-activation",
                    subject_type="connection",
                    subject_id=connection.public_id,
                    summary="Runtime connection access was disabled.",
                    data={"adapter_key": connection.adapter_key},
                    correlation_id=correlation_id,
                    occurred_at=now,
                )
            )
        if changed_ids:
            self._session.flush()
        return changed_ids

    def get(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
    ) -> ConnectionRecord | None:
        connection = self._scoped_connection(
            organization_public_id,
            connection_public_id,
        )
        return ConnectionRecord.model_validate(connection) if connection is not None else None

    def list(
        self,
        *,
        organization_public_id: str,
        health: str | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ConnectionPageRecord:
        organization = self._organization(organization_public_id)
        if organization is None:
            return ConnectionPageRecord(items=[], next_cursor=None, total=0)
        normalized_query = query.strip().lower() if query else None
        filters = [ConnectionModel.organization_id == organization.id]
        if health:
            filters.append(ConnectionModel.health == health)
        if normalized_query:
            pattern = f"%{normalized_query}%"
            filters.append(
                or_(
                    func.lower(ConnectionModel.public_id).like(pattern),
                    func.lower(ConnectionModel.name).like(pattern),
                    func.lower(ConnectionModel.provider_type).like(pattern),
                )
            )
        total_filters = list(filters)
        filter_fingerprint = _hash(
            {
                "organization": organization_public_id,
                "health": health,
                "query": normalized_query,
            }
        )
        cursor_values = _decode_cursor(cursor, filter_fingerprint) if cursor else None
        if cursor_values is not None:
            cursor_time, cursor_id = cursor_values
            filters.append(
                or_(
                    ConnectionModel.updated_at < cursor_time,
                    and_(
                        ConnectionModel.updated_at == cursor_time,
                        ConnectionModel.public_id > cursor_id,
                    ),
                )
            )
        rows = list(
            self._session.scalars(
                select(ConnectionModel)
                .where(*filters)
                .order_by(
                    ConnectionModel.updated_at.desc(),
                    ConnectionModel.public_id,
                )
                .limit(limit + 1)
            )
        )
        visible = rows[:limit]
        next_cursor = None
        if len(rows) > limit and visible:
            last = visible[-1]
            next_cursor = _encode_cursor(
                last.updated_at,
                last.public_id,
                filter_fingerprint,
            )
        total = self._session.scalar(select(func.count(ConnectionModel.id)).where(*total_filters))
        return ConnectionPageRecord(
            items=[ConnectionRecord.model_validate(item) for item in visible],
            next_cursor=next_cursor,
            total=total or 0,
        )

    def record_health_check(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
        actor_id: str,
        expected_version: int,
        health: ConnectionHealth,
        detail: str,
        correlation_id: str,
    ) -> tuple[ConnectionRecord, ConnectionHealthCheckRecord]:
        connection = self._required_connection(
            organization_public_id,
            connection_public_id,
            for_update=True,
        )
        if connection.version != expected_version:
            raise ConnectionVersionConflict(
                expected_version=expected_version,
                current_version=connection.version,
            )
        member = self._active_member(
            organization_id=connection.organization_id,
            actor_id=actor_id,
        )
        now = utc_now()
        receipt = ConnectionHealthCheckModel(
            public_id=_stable_public_id(
                "CH",
                organization_public_id,
                connection.public_id,
                str(connection.version),
            ),
            organization_id=connection.organization_id,
            connection_id=connection.id,
            health=health.value,
            detail=detail,
            checked_by_id=member.id,
            checked_by_public_id=member.public_id,
            checked_by_name=member.name,
            checked_at=now,
        )
        connection.health = health.value
        connection.last_checked_at = now
        connection.version += 1
        connection.updated_at = now
        self._session.add(receipt)
        self._session.add(
            AuditEventModel(
                organization_id=connection.organization_id,
                task_id=None,
                run_id=None,
                event_type="connection.health_checked",
                actor_type="member",
                actor_id=member.public_id,
                subject_type="connection",
                subject_id=connection.public_id,
                summary="Connection health was checked.",
                data={
                    "receipt_id": receipt.public_id,
                    "health": health.value,
                    "version": connection.version,
                },
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )
        self._session.flush()
        return (
            ConnectionRecord.model_validate(connection),
            ConnectionHealthCheckRecord.model_validate(receipt),
        )

    def resolve_for_action(
        self,
        *,
        organization_id: UUID,
        organization_public_id: str,
        action_type: str,
    ) -> ConnectionModel:
        candidates = list(
            self._session.scalars(
                select(ConnectionModel).where(ConnectionModel.organization_id == organization_id)
            )
        )
        compatible = [
            connection for connection in candidates if action_type in connection.action_types
        ]
        if compatible:
            return sorted(
                compatible,
                key=lambda item: (
                    _HEALTH_ORDER.get(item.health, 99),
                    _ENVIRONMENT_ORDER.get(item.environment, 99),
                    item.public_id,
                ),
            )[0]
        return self._ensure_unconfigured_connection(
            organization_id=organization_id,
            organization_public_id=organization_public_id,
            action_type=action_type,
        )

    def _ensure_unconfigured_connection(
        self,
        *,
        organization_id: UUID,
        organization_public_id: str,
        action_type: str,
    ) -> ConnectionModel:
        provider_type = _PROVIDER_BY_ACTION.get(action_type, "general_operations")
        public_id = _stable_public_id(
            "CN",
            organization_public_id,
            provider_type,
            "unconfigured",
        )
        existing = self._session.scalar(
            select(ConnectionModel).where(
                ConnectionModel.organization_id == organization_id,
                ConnectionModel.public_id == public_id,
            )
        )
        if existing is not None:
            if action_type not in existing.action_types:
                existing.action_types = sorted({*existing.action_types, action_type})
            return existing
        now = utc_now()
        connection = ConnectionModel(
            public_id=public_id,
            organization_id=organization_id,
            name=f"{_PROVIDER_LABEL.get(provider_type, 'General operations')} (not configured)",
            provider_type=provider_type,
            adapter_key="unconfigured",
            environment="demo",
            health=ConnectionHealth.NOT_CONFIGURED.value,
            last_checked_at=None,
            credential_status="missing",
            read_capabilities=[],
            write_capabilities=[],
            action_types=[action_type],
            affected_work=[],
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._session.add(connection)
        self._session.flush()
        return connection

    def _required_connection(
        self,
        organization_public_id: str,
        connection_public_id: str,
        *,
        for_update: bool = False,
    ) -> ConnectionModel:
        connection = self._scoped_connection(
            organization_public_id,
            connection_public_id,
            for_update=for_update,
        )
        if connection is None:
            raise ConnectionNotFound("The connection was not found.")
        return connection

    def _scoped_connection(
        self,
        organization_public_id: str,
        connection_public_id: str,
        *,
        for_update: bool = False,
    ) -> ConnectionModel | None:
        statement = (
            select(ConnectionModel)
            .join(
                OrganizationModel,
                OrganizationModel.id == ConnectionModel.organization_id,
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                ConnectionModel.public_id == connection_public_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def _organization(self, organization_public_id: str) -> OrganizationModel | None:
        return self._session.scalar(
            select(OrganizationModel).where(OrganizationModel.public_id == organization_public_id)
        )

    def _active_member(
        self,
        *,
        organization_id: UUID,
        actor_id: str,
    ) -> MembershipModel:
        member = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization_id,
                MembershipModel.status == "active",
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        )
        if member is None:
            raise ActorMembershipNotFound(
                "An active organization membership is required for this command."
            )
        return member


def _stable_public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _encode_cursor(
    updated_at: datetime,
    public_id: str,
    filter_fingerprint: str,
) -> str:
    payload = json.dumps(
        {
            "updated_at": updated_at.astimezone(UTC).isoformat(),
            "public_id": public_id,
            "filter": filter_fingerprint,
        },
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str, expected_filter: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        updated_at = datetime.fromisoformat(payload["updated_at"])
        public_id = str(payload["public_id"])
        filter_fingerprint = str(payload["filter"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidConnectionCursor("The connection cursor is invalid.") from exc
    if updated_at.tzinfo is None or filter_fingerprint != expected_filter:
        raise InvalidConnectionCursor("The connection cursor does not match these filters.")
    return updated_at.astimezone(UTC), public_id
