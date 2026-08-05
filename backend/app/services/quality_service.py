from typing import Protocol

from app.domain.identity import ActorContext, Permission
from app.domain.quality import (
    CaseQualityProjectionRecord,
    QualityCategory,
    QualityDashboardRecord,
    QualityProjectionNotFound,
)
from app.security.authorization import require_permission


class QualityStore(Protocol):
    def dashboard(
        self,
        *,
        organization_public_id: str,
        category: QualityCategory | None,
        limit: int,
    ) -> QualityDashboardRecord: ...

    def get_case(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> list[CaseQualityProjectionRecord] | None: ...


class QualityService:
    def __init__(self, store: QualityStore) -> None:
        self._store = store

    def dashboard(
        self,
        *,
        actor: ActorContext,
        category: QualityCategory | None,
        limit: int,
    ) -> QualityDashboardRecord:
        require_permission(actor, Permission.QUALITY_READ)
        return self._store.dashboard(
            organization_public_id=actor.organization_id,
            category=category,
            limit=limit,
        )

    def get_case(
        self,
        *,
        actor: ActorContext,
        case_id: str,
    ) -> list[CaseQualityProjectionRecord]:
        require_permission(actor, Permission.QUALITY_READ)
        records = self._store.get_case(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )
        if records is None:
            raise QualityProjectionNotFound("The evaluated case was not found.")
        return records
