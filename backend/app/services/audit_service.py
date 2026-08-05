from typing import Protocol

from app.domain.audit import CaseAuditExportRecord
from app.domain.identity import ActorContext, Permission
from app.security.authorization import require_permission


class CaseAuditStore(Protocol):
    def export(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        correlation_id: str,
    ) -> CaseAuditExportRecord: ...


class CaseAuditService:
    def __init__(self, store: CaseAuditStore) -> None:
        self._store = store

    def export(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        correlation_id: str,
    ) -> CaseAuditExportRecord:
        require_permission(actor, Permission.AUDIT_READ)
        return self._store.export(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            correlation_id=correlation_id,
        )
