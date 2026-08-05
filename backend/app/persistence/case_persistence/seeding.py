from datetime import datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select, text

from app.domain.cases import (
    CaseCreate,
    CaseNotFound,
    CaseSeedConflict,
    CaseWorkspaceRecord,
    MessageAuthorType,
)
from app.persistence.data_governance_repository import DataGovernanceRepository
from app.persistence.models import (
    BusinessObjectSnapshotModel,
    CaseCustomerModel,
    CaseModel,
    CaseRequestModel,
    ConversationMessageModel,
    ConversationThreadModel,
    OrganizationModel,
    ResponseDraftModel,
)

from ._base import CaseRepositoryBase


class CaseSeedRepository(CaseRepositoryBase):
    def seed_case(
        self,
        *,
        organization_public_id: str,
        command: CaseCreate,
        correlation_id: str,
        legacy_task_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        customer_captured_at: datetime | None = None,
    ) -> CaseWorkspaceRecord:
        workspace, _ = self.seed_case_with_status(
            organization_public_id=organization_public_id,
            command=command,
            correlation_id=correlation_id,
            legacy_task_id=legacy_task_id,
            created_at=created_at,
            updated_at=updated_at,
            customer_captured_at=customer_captured_at,
        )
        return workspace

    def seed_case_with_status(
        self,
        *,
        organization_public_id: str,
        command: CaseCreate,
        correlation_id: str,
        legacy_task_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        customer_captured_at: datetime | None = None,
    ) -> tuple[CaseWorkspaceRecord, bool]:
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {
                "lock_key": int.from_bytes(
                    sha256(f"{organization_public_id}:{command.source_id}".encode()).digest()[:8],
                    byteorder="big",
                    signed=True,
                )
            },
        )
        if legacy_task_id is not None:
            lineage_case_id = self._session.scalar(
                select(CaseModel.public_id)
                .join(OrganizationModel, OrganizationModel.id == CaseModel.organization_id)
                .where(
                    OrganizationModel.public_id == organization_public_id,
                    CaseModel.legacy_task_id == legacy_task_id,
                )
            )
            if lineage_case_id is not None:
                if lineage_case_id != command.public_id:
                    raise CaseSeedConflict(
                        "The legacy task is already linked to a different generic case."
                    )
                return (
                    self._required_workspace(
                        organization_public_id,
                        lineage_case_id,
                    ),
                    False,
                )
        existing = self.get_workspace(
            organization_public_id=organization_public_id,
            case_public_id=command.public_id,
        )
        if existing is not None:
            if (
                existing.case.legacy_task_id != legacy_task_id
                or existing.case.source_id != command.source_id
                or not self._matches_seed(existing, command)
            ):
                raise CaseSeedConflict(
                    f"Case {command.public_id} already exists with a different source lineage."
                )
            return existing, False
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise CaseNotFound("The target organization was not found.")

        case_uuid = uuid4()
        thread_uuid = uuid4()
        case = CaseModel(
            id=case_uuid,
            public_id=command.public_id,
            organization_id=organization_id,
            legacy_task_id=legacy_task_id,
            source_id=command.source_id,
            external_reference=command.external_reference,
            category=command.category.value,
            issue=command.issue,
            status=command.status.value,
            owner_id=None,
            urgency=command.urgency.value,
            risk=command.risk.value,
            due_at=command.due_at,
            impact_amount=command.impact_amount,
            impact_currency=command.impact_currency,
            source_freshness=command.source_freshness.value,
            source_checked_at=command.source_checked_at,
            version=1,
            created_at=created_at or command.request.received_at,
            updated_at=updated_at or command.source_checked_at or command.request.received_at,
        )
        request = CaseRequestModel(
            public_id=f"REQ-{command.public_id}",
            organization_id=organization_id,
            case_id=case_uuid,
            channel=command.request.channel.value,
            customer_message=command.request.customer_message,
            summary=command.request.summary,
            received_at=command.request.received_at,
        )
        customer = CaseCustomerModel(
            organization_id=organization_id,
            case_id=case_uuid,
            customer_id=command.customer.customer_id,
            name=command.customer.name,
            tier=command.customer.tier.value,
            locale=command.customer.locale,
            contact=command.customer.contact,
            captured_at=customer_captured_at or command.request.received_at,
        )
        thread = ConversationThreadModel(
            id=thread_uuid,
            public_id=f"CV-{command.public_id}",
            organization_id=organization_id,
            case_id=case_uuid,
            version=1,
            updated_at=command.request.received_at,
        )
        initial_message = ConversationMessageModel(
            public_id=f"MSG-{command.public_id}-001",
            organization_id=organization_id,
            case_id=case_uuid,
            thread_id=thread_uuid,
            author_type=MessageAuthorType.CUSTOMER.value,
            author_id=command.customer.customer_id,
            author_name=command.customer.name,
            channel=command.request.channel.value,
            body=command.request.customer_message,
            internal=False,
            source_reference=command.external_reference,
            version=1,
            created_at=command.request.received_at,
        )
        draft = ResponseDraftModel(
            public_id=f"DFT-{command.public_id}",
            organization_id=organization_id,
            case_id=case_uuid,
            subject=f"Re: {command.issue}"[:300],
            body=(
                f"Hello {command.customer.name},\n\n"
                "We received your request and are reviewing the available information."
            ),
            status="draft",
            version=1,
            updated_at=command.request.received_at,
        )
        business_objects = [
            BusinessObjectSnapshotModel(
                public_id=context.public_id,
                organization_id=organization_id,
                case_id=case_uuid,
                object_type=context.type.value,
                label=context.label,
                source=context.source,
                source_reference=context.source_reference,
                status=context.status,
                fields=context.fields,
                captured_at=context.captured_at,
                source_freshness=context.freshness.value,
                source_checked_at=context.checked_at,
                version=1,
            )
            for context in command.business_contexts
        ]
        # Persist the tenant-scoped parent before unrelated ORM mappers reference its composite key.
        self._session.add(case)
        self._session.flush()
        self._session.add_all([request, customer, thread, draft, *business_objects])
        self._session.flush()
        self._session.add(initial_message)
        self._session.flush()
        self._audit(
            case=case,
            actor_id=None,
            actor_type="system",
            event_type="case.imported",
            summary="Case imported from a configured case source.",
            data={"source_id": command.source_id},
            correlation_id=correlation_id,
        )
        DataGovernanceRepository(self._session).backfill(
            organization_public_id=organization_public_id,
            apply=True,
        )
        self._session.flush()
        return (
            self._required_workspace(
                organization_public_id,
                command.public_id,
            ),
            True,
        )

    @staticmethod
    def _matches_seed(existing: CaseWorkspaceRecord, command: CaseCreate) -> bool:
        case = existing.case
        if (
            case.external_reference != command.external_reference
            or case.category != command.category
            or case.issue != command.issue
            or case.urgency != command.urgency
            or case.risk != command.risk
            or case.due_at != command.due_at
            or case.impact_amount != command.impact_amount
            or case.impact_currency != command.impact_currency
            or case.source_freshness != command.source_freshness
            or case.source_checked_at != command.source_checked_at
        ):
            return False
        request = existing.request
        if (
            request.channel != command.request.channel
            or request.customer_message != command.request.customer_message
            or request.summary != command.request.summary
            or request.received_at != command.request.received_at
        ):
            return False
        customer = existing.customer
        if (
            customer.customer_id != command.customer.customer_id
            or customer.name != command.customer.name
            or customer.tier != command.customer.tier
            or customer.locale != command.customer.locale
            or customer.contact != command.customer.contact
        ):
            return False
        current_contexts = {
            item.public_id: (
                item.type,
                item.label,
                item.source,
                item.source_reference,
                item.status,
                item.fields,
                item.captured_at,
                item.source_freshness,
                item.source_checked_at,
            )
            for item in existing.business_contexts
        }
        expected_contexts = {
            item.public_id: (
                item.type,
                item.label,
                item.source,
                item.source_reference,
                item.status,
                item.fields,
                item.captured_at,
                item.freshness,
                item.checked_at,
            )
            for item in command.business_contexts
        }
        return current_contexts == expected_contexts
