from sqlalchemy import and_, func, or_, select

from app.domain.actions import (
    ActionPageRecord,
    ActionQueueItemRecord,
)
from app.persistence.models import (
    CaseActionModel,
    CaseModel,
    ConnectionModel,
    utc_now,
)

from ._base import (
    _RECOVERY_STATUSES,
    ActionRepositoryBase,
    _decode_cursor,
    _encode_cursor,
    _hash,
)


class ActionQueryRepository(ActionRepositoryBase):
    def get(
        self,
        *,
        organization_public_id: str,
        action_public_id: str,
    ) -> ActionQueueItemRecord | None:
        action = self._scoped_action(
            organization_public_id,
            action_public_id,
        )
        if action is None:
            return None
        self._reconcile_abandoned(action=action, now=utc_now())
        return self._queue_item(action, now=utc_now())

    def list(
        self,
        *,
        organization_public_id: str,
        status: str | None,
        recovery_required: bool | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ActionPageRecord:
        organization = self._organization(organization_public_id)
        if organization is None:
            return ActionPageRecord(items=[], next_cursor=None, total=0)
        now = utc_now()
        self._reconcile_abandoned(
            organization_id=organization.id,
            now=now,
        )
        normalized_query = query.strip().lower() if query else None
        filters = [CaseActionModel.organization_id == organization.id]
        if status:
            filters.append(CaseActionModel.status == status)
        if recovery_required is True:
            filters.append(CaseActionModel.status.in_(_RECOVERY_STATUSES))
        elif recovery_required is False:
            filters.append(CaseActionModel.status.not_in(_RECOVERY_STATUSES))
        if normalized_query:
            pattern = f"%{normalized_query}%"
            filters.append(
                or_(
                    func.lower(CaseActionModel.public_id).like(pattern),
                    func.lower(CaseActionModel.label).like(pattern),
                    func.lower(CaseActionModel.type).like(pattern),
                    func.lower(CaseActionModel.target).like(pattern),
                    func.lower(CaseModel.public_id).like(pattern),
                    func.lower(ConnectionModel.name).like(pattern),
                )
            )
        total_filters = list(filters)
        filter_fingerprint = _hash(
            {
                "organization": organization_public_id,
                "status": status,
                "recovery_required": recovery_required,
                "query": normalized_query,
            }
        )
        cursor_values = _decode_cursor(cursor, filter_fingerprint) if cursor else None
        if cursor_values is not None:
            cursor_time, cursor_id = cursor_values
            filters.append(
                or_(
                    CaseActionModel.updated_at < cursor_time,
                    and_(
                        CaseActionModel.updated_at == cursor_time,
                        CaseActionModel.public_id > cursor_id,
                    ),
                )
            )
        base = (
            select(CaseActionModel)
            .join(CaseModel, CaseModel.id == CaseActionModel.case_id)
            .join(ConnectionModel, ConnectionModel.id == CaseActionModel.connection_id)
        )
        rows = list(
            self._session.scalars(
                base.where(*filters)
                .order_by(
                    CaseActionModel.updated_at.desc(),
                    CaseActionModel.public_id,
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
        total = self._session.scalar(
            select(func.count(CaseActionModel.id))
            .select_from(CaseActionModel)
            .join(CaseModel, CaseModel.id == CaseActionModel.case_id)
            .join(ConnectionModel, ConnectionModel.id == CaseActionModel.connection_id)
            .where(*total_filters)
        )
        return ActionPageRecord(
            items=[self._queue_item(action, now=now) for action in visible],
            next_cursor=next_cursor,
            total=total or 0,
        )
