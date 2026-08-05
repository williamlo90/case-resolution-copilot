from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.domain.cases import (
    BusinessObjectRecord,
    CaseActivityPageRecord,
    CaseActivityRecord,
    CaseCollectionWindowRecord,
    CaseConcurrencyConflict,
    CaseHistoryPosition,
    CaseNotFound,
    CaseOwnerRecord,
    CaseRecord,
    CaseRequestRecord,
    CaseWorkspaceCollectionsRecord,
    CaseWorkspaceRecord,
    ConversationMessagePageRecord,
    ConversationMessageRecord,
    ConversationThreadRecord,
    CustomerContextRecord,
    ResponseDraftRecord,
)
from app.persistence.models import (
    AuditEventModel,
    BusinessObjectSnapshotModel,
    CaseCustomerModel,
    CaseModel,
    CaseRequestModel,
    ConversationMessageModel,
    ConversationThreadModel,
    MembershipModel,
    OrganizationModel,
    ResponseDraftModel,
    utc_now,
)

CASE_WORKSPACE_BUSINESS_CONTEXT_LIMIT = 100
CASE_WORKSPACE_MESSAGE_LIMIT = 50
CASE_WORKSPACE_ACTIVITY_LIMIT = 100


class CaseRepositoryBase:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_workspace(
        self, *, organization_public_id: str, case_public_id: str
    ) -> CaseWorkspaceRecord | None:
        owner = aliased(MembershipModel)
        row = self._session.execute(
            select(
                CaseModel,
                CaseRequestModel,
                CaseCustomerModel,
                ConversationThreadModel,
                ResponseDraftModel,
                owner,
            )
            .join(
                OrganizationModel,
                OrganizationModel.id == CaseModel.organization_id,
            )
            .join(
                CaseRequestModel,
                and_(
                    CaseRequestModel.organization_id == CaseModel.organization_id,
                    CaseRequestModel.case_id == CaseModel.id,
                ),
            )
            .join(
                CaseCustomerModel,
                and_(
                    CaseCustomerModel.organization_id == CaseModel.organization_id,
                    CaseCustomerModel.case_id == CaseModel.id,
                ),
            )
            .join(
                ConversationThreadModel,
                and_(
                    ConversationThreadModel.organization_id == CaseModel.organization_id,
                    ConversationThreadModel.case_id == CaseModel.id,
                ),
            )
            .outerjoin(
                ResponseDraftModel,
                and_(
                    ResponseDraftModel.organization_id == CaseModel.organization_id,
                    ResponseDraftModel.case_id == CaseModel.id,
                ),
            )
            .outerjoin(
                owner,
                and_(
                    owner.organization_id == CaseModel.organization_id,
                    owner.id == CaseModel.owner_id,
                ),
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
        ).one_or_none()
        if row is None:
            return None

        case, request, customer, thread, draft, member = row
        business_total = int(
            self._session.scalar(
                select(func.count(BusinessObjectSnapshotModel.id)).where(
                    BusinessObjectSnapshotModel.organization_id == case.organization_id,
                    BusinessObjectSnapshotModel.case_id == case.id,
                )
            )
            or 0
        )
        business_models = list(
            self._session.scalars(
                select(BusinessObjectSnapshotModel)
                .where(
                    BusinessObjectSnapshotModel.organization_id == case.organization_id,
                    BusinessObjectSnapshotModel.case_id == case.id,
                )
                .order_by(
                    BusinessObjectSnapshotModel.captured_at.desc(),
                    BusinessObjectSnapshotModel.public_id.desc(),
                )
                .limit(CASE_WORKSPACE_BUSINESS_CONTEXT_LIMIT)
            )
        )
        business_models.sort(key=lambda model: model.public_id)
        message_page = self._conversation_page(
            case=case,
            before=None,
            limit=CASE_WORKSPACE_MESSAGE_LIMIT,
        )
        activity_page = self._activity_page(
            case=case,
            before=None,
            limit=CASE_WORKSPACE_ACTIVITY_LIMIT,
        )
        business_returned = len(business_models)
        return CaseWorkspaceRecord(
            case=CaseRecord.model_validate(case),
            request=CaseRequestRecord.model_validate(request),
            customer=CustomerContextRecord.model_validate(customer),
            business_contexts=[self._business_record(model) for model in business_models],
            owner=self._owner_record(member),
            thread=ConversationThreadRecord.model_validate(thread),
            messages=message_page.items,
            draft=ResponseDraftRecord.model_validate(draft) if draft else None,
            activity=activity_page.items,
            collections=CaseWorkspaceCollectionsRecord(
                business_contexts=CaseCollectionWindowRecord(
                    returned=business_returned,
                    total=business_total,
                    has_more=business_returned < business_total,
                ),
                messages=CaseCollectionWindowRecord(
                    returned=len(message_page.items),
                    total=message_page.total,
                    has_more=message_page.next_position is not None,
                    next_position=message_page.next_position,
                ),
                activity=CaseCollectionWindowRecord(
                    returned=len(activity_page.items),
                    total=activity_page.total,
                    has_more=activity_page.next_position is not None,
                    next_position=activity_page.next_position,
                ),
            ),
        )

    def _conversation_page(
        self,
        *,
        case: CaseModel,
        before: CaseHistoryPosition | None,
        limit: int,
    ) -> ConversationMessagePageRecord:
        filters = [
            ConversationMessageModel.organization_id == case.organization_id,
            ConversationMessageModel.case_id == case.id,
        ]
        if before is not None:
            filters.append(
                or_(
                    ConversationMessageModel.created_at < before.occurred_at,
                    and_(
                        ConversationMessageModel.created_at == before.occurred_at,
                        ConversationMessageModel.public_id < before.tie_breaker,
                    ),
                )
            )
        total = int(
            self._session.scalar(
                select(func.count(ConversationMessageModel.id)).where(
                    ConversationMessageModel.organization_id == case.organization_id,
                    ConversationMessageModel.case_id == case.id,
                )
            )
            or 0
        )
        models = list(
            self._session.scalars(
                select(ConversationMessageModel)
                .where(*filters)
                .order_by(
                    ConversationMessageModel.created_at.desc(),
                    ConversationMessageModel.public_id.desc(),
                )
                .limit(limit + 1)
            )
        )
        has_more = len(models) > limit
        page_models = models[:limit]
        oldest = page_models[-1] if has_more and page_models else None
        return ConversationMessagePageRecord(
            items=[
                ConversationMessageRecord.model_validate(model)
                for model in reversed(page_models)
            ],
            total=total,
            next_position=(
                CaseHistoryPosition(
                    occurred_at=oldest.created_at,
                    tie_breaker=oldest.public_id,
                )
                if oldest is not None
                else None
            ),
        )

    def _activity_page(
        self,
        *,
        case: CaseModel,
        before: CaseHistoryPosition | None,
        limit: int,
    ) -> CaseActivityPageRecord:
        filters = [
            AuditEventModel.organization_id == case.organization_id,
            AuditEventModel.subject_type == "case",
            AuditEventModel.subject_id == case.public_id,
        ]
        if before is not None:
            filters.append(
                or_(
                    AuditEventModel.occurred_at < before.occurred_at,
                    and_(
                        AuditEventModel.occurred_at == before.occurred_at,
                        AuditEventModel.id < UUID(before.tie_breaker),
                    ),
                )
            )
        total = int(
            self._session.scalar(
                select(func.count(AuditEventModel.id)).where(
                    AuditEventModel.organization_id == case.organization_id,
                    AuditEventModel.subject_type == "case",
                    AuditEventModel.subject_id == case.public_id,
                )
            )
            or 0
        )
        models = list(
            self._session.scalars(
                select(AuditEventModel)
                .where(*filters)
                .order_by(
                    AuditEventModel.occurred_at.desc(),
                    AuditEventModel.id.desc(),
                )
                .limit(limit + 1)
            )
        )
        has_more = len(models) > limit
        page_models = models[:limit]
        oldest = page_models[-1] if has_more and page_models else None
        return CaseActivityPageRecord(
            items=[
                CaseActivityRecord(
                    id=model.id,
                    event_type=model.event_type,
                    actor_id=model.actor_id,
                    summary=model.summary or model.event_type,
                    occurred_at=model.occurred_at,
                )
                for model in reversed(page_models)
            ],
            total=total,
            next_position=(
                CaseHistoryPosition(
                    occurred_at=oldest.occurred_at,
                    tie_breaker=str(oldest.id),
                )
                if oldest is not None
                else None
            ),
        )

    def _organization_id(self, public_id: str) -> UUID | None:
        return self._session.scalar(
            select(OrganizationModel.id).where(OrganizationModel.public_id == public_id)
        )

    def _required_case(self, organization_public_id: str, case_public_id: str) -> CaseModel:
        model = self._session.scalar(
            select(CaseModel)
            .join(OrganizationModel, OrganizationModel.id == CaseModel.organization_id)
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
            )
        )
        if model is None:
            raise CaseNotFound("The case was not found.")
        return model

    def _required_workspace(
        self, organization_public_id: str, case_public_id: str
    ) -> CaseWorkspaceRecord:
        workspace = self.get_workspace(
            organization_public_id=organization_public_id,
            case_public_id=case_public_id,
        )
        if workspace is None:
            raise CaseNotFound("The case was not found.")
        return workspace

    def _update_case(
        self,
        *,
        case: CaseModel,
        expected_version: int,
        values: dict[str, object],
    ) -> CaseModel:
        statement = (
            update(CaseModel)
            .where(
                CaseModel.id == case.id,
                CaseModel.organization_id == case.organization_id,
                CaseModel.version == expected_version,
            )
            .values(
                **values,
                version=CaseModel.version + 1,
                updated_at=utc_now(),
            )
            .returning(CaseModel)
        )
        updated = self._session.scalar(statement)
        if updated is None:
            current_version = self._session.scalar(
                select(CaseModel.version).where(
                    CaseModel.id == case.id,
                    CaseModel.organization_id == case.organization_id,
                )
            )
            if current_version is None:
                raise CaseNotFound("The case was not found.")
            raise CaseConcurrencyConflict(
                expected_version=expected_version,
                current_version=current_version,
            )
        return updated

    def _audit(
        self,
        *,
        case: CaseModel,
        actor_id: str | None,
        actor_type: str,
        event_type: str,
        summary: str,
        data: dict[str, object],
        correlation_id: str,
    ) -> None:
        self._session.add(
            AuditEventModel(
                organization_id=case.organization_id,
                task_id=None,
                run_id=None,
                event_type=event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                subject_type="case",
                subject_id=case.public_id,
                summary=summary,
                data=data,
                correlation_id=correlation_id,
            )
        )

    @staticmethod
    def _owner_record(model: MembershipModel | None) -> CaseOwnerRecord | None:
        if model is None:
            return None
        return CaseOwnerRecord(id=model.id, public_id=model.public_id, name=model.name)

    @staticmethod
    def _business_record(model: BusinessObjectSnapshotModel) -> BusinessObjectRecord:
        return BusinessObjectRecord(
            id=model.id,
            public_id=model.public_id,
            organization_id=model.organization_id,
            case_id=model.case_id,
            type=model.object_type,
            label=model.label,
            source=model.source,
            source_reference=model.source_reference,
            status=model.status,
            fields=model.fields,
            captured_at=model.captured_at,
            source_freshness=model.source_freshness,
            source_checked_at=model.source_checked_at,
            version=model.version,
        )
