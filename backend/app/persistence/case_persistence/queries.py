from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, func, or_, select, union
from sqlalchemy.orm import aliased

from app.domain.cases import (
    CaseActivityPageRecord,
    CaseCategory,
    CaseHistoryPosition,
    CaseListItemRecord,
    CaseListPageRecord,
    CaseNotFound,
    CaseQueueCursorDirection,
    CaseQueueCursorRecord,
    CaseQueuePosition,
    CaseQueueSort,
    CaseQueueSummaryRecord,
    CaseQueueView,
    CaseRecord,
    CaseStatus,
    ConversationMessagePageRecord,
    CustomerContextRecord,
)
from app.persistence.models import (
    CaseCustomerModel,
    CaseModel,
    MembershipModel,
)

from ._base import CaseRepositoryBase


class CaseQueryRepository(CaseRepositoryBase):
    def list_conversation_messages(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        before: CaseHistoryPosition | None,
        limit: int,
    ) -> ConversationMessagePageRecord:
        case_record = self._required_case(organization_public_id, case_public_id)
        return self._conversation_page(case=case_record, before=before, limit=limit)

    def list_case_activity(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        before: CaseHistoryPosition | None,
        limit: int,
    ) -> CaseActivityPageRecord:
        case_record = self._required_case(organization_public_id, case_public_id)
        return self._activity_page(case=case_record, before=before, limit=limit)

    def list_cases(
        self,
        *,
        organization_public_id: str,
        status: CaseStatus | None,
        category: CaseCategory | None,
        query: str | None,
        cursor: CaseQueueCursorRecord | None,
        limit: int,
        actor_public_id: str,
        view: CaseQueueView,
        sort: CaseQueueSort,
    ) -> CaseListPageRecord:
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise CaseNotFound("The actor organization was not found.")

        owner = aliased(MembershipModel)
        snapshot_at = cursor.snapshot_at if cursor is not None else datetime.now(UTC)
        filters = [
            CaseModel.organization_id == organization_id,
            CaseModel.updated_at <= snapshot_at,
        ]
        if status is not None:
            filters.append(CaseModel.status == status.value)
        if category is not None:
            filters.append(CaseModel.category == category.value)
        if query:
            escaped_query = (
                query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            term = f"%{escaped_query}%"
            searchable_cases = CaseModel.__table__.alias("searchable_cases")
            searchable_customers = CaseCustomerModel.__table__.alias("searchable_customers")
            matching_case_ids = union(
                select(searchable_cases.c.id.label("case_id")).where(
                    searchable_cases.c.organization_id == organization_id,
                    searchable_cases.c.public_id.ilike(term, escape="\\"),
                ),
                select(searchable_cases.c.id.label("case_id")).where(
                    searchable_cases.c.organization_id == organization_id,
                    searchable_cases.c.external_reference.ilike(term, escape="\\"),
                ),
                select(searchable_cases.c.id.label("case_id")).where(
                    searchable_cases.c.organization_id == organization_id,
                    searchable_cases.c.issue.ilike(term, escape="\\"),
                ),
                select(searchable_customers.c.case_id.label("case_id")).where(
                    searchable_customers.c.organization_id == organization_id,
                    searchable_customers.c.name.ilike(term, escape="\\"),
                ),
            ).subquery("matching_case_ids")
            filters.append(CaseModel.id.in_(select(matching_case_ids.c.case_id)))
        sla_cutoff = snapshot_at + timedelta(minutes=30)
        if view is CaseQueueView.MINE:
            filters.append(
                or_(
                    owner.public_id == actor_public_id,
                    owner.subject_id == actor_public_id,
                )
            )
        elif view is CaseQueueView.UNASSIGNED:
            filters.append(CaseModel.owner_id.is_(None))
        elif view is CaseQueueView.REVIEW:
            filters.append(CaseModel.status == CaseStatus.NEEDS_REVIEW.value)
        elif view is CaseQueueView.AT_RISK:
            filters.append(
                or_(
                    CaseModel.risk == "high",
                    CaseModel.due_at < sla_cutoff,
                )
            )
        scope_filters = tuple(filters)

        risk_order = case(
            (CaseModel.risk == "high", 0),
            (CaseModel.risk == "medium", 1),
            else_=2,
        )
        backward = cursor is not None and cursor.direction is CaseQueueCursorDirection.BACKWARD
        if cursor is not None:
            position = cursor.position
            if sort is CaseQueueSort.PRIORITY:
                assert position.risk_rank is not None
                after = or_(
                    risk_order > position.risk_rank,
                    and_(
                        risk_order == position.risk_rank,
                        CaseModel.due_at > position.ordered_at,
                    ),
                    and_(
                        risk_order == position.risk_rank,
                        CaseModel.due_at == position.ordered_at,
                        CaseModel.public_id > position.public_id,
                    ),
                )
                before = or_(
                    risk_order < position.risk_rank,
                    and_(
                        risk_order == position.risk_rank,
                        CaseModel.due_at < position.ordered_at,
                    ),
                    and_(
                        risk_order == position.risk_rank,
                        CaseModel.due_at == position.ordered_at,
                        CaseModel.public_id < position.public_id,
                    ),
                )
            elif sort is CaseQueueSort.SLA:
                after = or_(
                    CaseModel.due_at > position.ordered_at,
                    and_(
                        CaseModel.due_at == position.ordered_at,
                        CaseModel.public_id > position.public_id,
                    ),
                )
                before = or_(
                    CaseModel.due_at < position.ordered_at,
                    and_(
                        CaseModel.due_at == position.ordered_at,
                        CaseModel.public_id < position.public_id,
                    ),
                )
            else:
                after = or_(
                    CaseModel.updated_at < position.ordered_at,
                    and_(
                        CaseModel.updated_at == position.ordered_at,
                        CaseModel.public_id > position.public_id,
                    ),
                )
                before = or_(
                    CaseModel.updated_at > position.ordered_at,
                    and_(
                        CaseModel.updated_at == position.ordered_at,
                        CaseModel.public_id < position.public_id,
                    ),
                )
            filters.append(before if backward else after)

        total = self._session.scalar(
            select(func.count(CaseModel.id))
            .join(
                CaseCustomerModel,
                and_(
                    CaseCustomerModel.organization_id == CaseModel.organization_id,
                    CaseCustomerModel.case_id == CaseModel.id,
                ),
            )
            .outerjoin(
                owner,
                and_(
                    owner.organization_id == CaseModel.organization_id,
                    owner.id == CaseModel.owner_id,
                ),
            )
            .where(*scope_filters)
        )
        page_query = (
            select(CaseModel, CaseCustomerModel, owner)
            .join(
                CaseCustomerModel,
                and_(
                    CaseCustomerModel.organization_id == CaseModel.organization_id,
                    CaseCustomerModel.case_id == CaseModel.id,
                ),
            )
            .outerjoin(
                owner,
                and_(
                    owner.organization_id == CaseModel.organization_id,
                    owner.id == CaseModel.owner_id,
                ),
            )
            .where(*filters)
        )
        if backward:
            if sort is CaseQueueSort.PRIORITY:
                page_query = page_query.order_by(
                    risk_order.desc(),
                    CaseModel.due_at.desc(),
                    CaseModel.public_id.desc(),
                )
            elif sort is CaseQueueSort.SLA:
                page_query = page_query.order_by(
                    CaseModel.due_at.desc(),
                    CaseModel.public_id.desc(),
                )
            else:
                page_query = page_query.order_by(
                    CaseModel.updated_at,
                    CaseModel.public_id.desc(),
                )
        elif sort is CaseQueueSort.PRIORITY:
            page_query = page_query.order_by(
                risk_order,
                CaseModel.due_at,
                CaseModel.public_id,
            )
        elif sort is CaseQueueSort.SLA:
            page_query = page_query.order_by(
                CaseModel.due_at,
                CaseModel.public_id,
            )
        else:
            page_query = page_query.order_by(
                CaseModel.updated_at.desc(),
                CaseModel.public_id,
            )
        rows = list(self._session.execute(page_query.limit(limit + 1)).all())
        has_extra = len(rows) > limit
        page_rows = rows[:limit]
        if backward:
            page_rows.reverse()
        total_count = total or 0
        items = [
            CaseListItemRecord(
                case=CaseRecord.model_validate(case_model),
                customer=CustomerContextRecord.model_validate(customer),
                owner=self._owner_record(member),
            )
            for case_model, customer, member in page_rows
        ]
        offset = cursor.offset if cursor is not None else 0
        has_previous = has_extra if backward else cursor is not None and bool(items)
        has_next = cursor is not None and bool(items) if backward else has_extra
        first_position = _case_queue_position(page_rows[0][0], sort=sort) if page_rows else None
        last_position = _case_queue_position(page_rows[-1][0], sort=sort) if page_rows else None
        previous_cursor = (
            CaseQueueCursorRecord(
                direction=CaseQueueCursorDirection.BACKWARD,
                offset=max(0, offset - limit),
                snapshot_at=snapshot_at,
                position=first_position,
            )
            if has_previous and first_position is not None
            else None
        )
        next_cursor = (
            CaseQueueCursorRecord(
                direction=CaseQueueCursorDirection.FORWARD,
                offset=offset + len(items),
                snapshot_at=snapshot_at,
                position=last_position,
            )
            if has_next and last_position is not None
            else None
        )
        summary_row = self._session.execute(
            select(
                func.count(CaseModel.id),
                func.count(CaseModel.id).filter(CaseModel.risk == "high"),
                func.count(CaseModel.id).filter(CaseModel.status == CaseStatus.NEEDS_REVIEW.value),
                func.count(CaseModel.id).filter(CaseModel.due_at < sla_cutoff),
                func.count(CaseModel.id).filter(CaseModel.owner_id.is_(None)),
            ).where(CaseModel.organization_id == organization_id)
        ).one()
        summary = CaseQueueSummaryRecord(
            total=int(summary_row[0] or 0),
            attention=int(summary_row[1] or 0),
            review=int(summary_row[2] or 0),
            sla_at_risk=int(summary_row[3] or 0),
            unassigned=int(summary_row[4] or 0),
        )
        return CaseListPageRecord(
            items=items,
            next_cursor=next_cursor,
            previous_cursor=previous_cursor,
            total=total_count,
            offset=offset,
            limit=limit,
            summary=summary,
        )


def _case_queue_position(
    case_model: CaseModel,
    *,
    sort: CaseQueueSort,
) -> CaseQueuePosition:
    return CaseQueuePosition(
        ordered_at=(case_model.updated_at if sort is CaseQueueSort.UPDATED else case_model.due_at),
        public_id=case_model.public_id,
        risk_rank=(
            {"high": 0, "medium": 1, "low": 2}[case_model.risk]
            if sort is CaseQueueSort.PRIORITY
            else None
        ),
    )
