from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select

from app.domain.inbox import (
    ImportedCaseHandle,
    MessageDirection,
    ProviderMessage,
    ProviderThread,
    SelectedThreadImportCommand,
)
from app.persistence.data_governance_repository import DataGovernanceRepository
from app.persistence.models import (
    CaseCustomerModel,
    CaseModel,
    CaseRequestModel,
    ConversationThreadModel,
)

from ._base import CaseRepositoryBase
from .inbox_message_factory import build_inbox_message


class CaseInboxWriter(CaseRepositoryBase):
    def case_public_id(
        self,
        *,
        organization_public_id: str,
        case_id: UUID,
    ) -> str:
        organization_id = self._organization_id(organization_public_id)
        public_id = self._session.scalar(
            select(CaseModel.public_id).where(
                CaseModel.organization_id == organization_id,
                CaseModel.id == case_id,
            )
        )
        if public_id is None:
            raise LookupError("The imported case was not found.")
        return public_id

    def create_case(
        self,
        *,
        organization_public_id: str,
        connection_public_id: str,
        thread: ProviderThread,
        command: SelectedThreadImportCommand,
        correlation_id: str,
    ) -> ImportedCaseHandle:
        organization_id = self._organization_id(organization_public_id)
        if organization_id is None:
            raise LookupError("The target workspace was not found.")
        messages = sorted(
            thread.messages,
            key=lambda item: (item.received_at, item.provider_message_id),
        )
        first = messages[0]
        customer_message = next(
            (item for item in messages if item.direction is MessageDirection.INBOUND),
            first,
        )
        source_digest = sha256(
            f"{connection_public_id}\0{thread.provider_thread_id}".encode()
        ).hexdigest()
        source_id = f"inbox:{source_digest}"
        if self._session.scalar(
            select(CaseModel.id).where(
                CaseModel.organization_id == organization_id,
                CaseModel.source_id == source_id,
            )
        ):
            raise RuntimeError("The selected inbox thread already has a case.")

        case_id = uuid4()
        thread_id = uuid4()
        local_message_id = uuid4()
        case_public_id = f"CS-EMAIL-{source_digest[:12].upper()}"
        case = CaseModel(
            id=case_id,
            public_id=case_public_id,
            organization_id=organization_id,
            legacy_task_id=None,
            source_id=source_id,
            external_reference=f"EMAIL-{source_digest[:16].upper()}",
            category=command.category.value,
            issue=first.subject[:500],
            status="new",
            owner_id=None,
            urgency=command.urgency.value,
            risk=command.risk.value,
            due_at=command.due_at,
            impact_amount=None,
            impact_currency=None,
            source_freshness="current",
            source_checked_at=messages[-1].received_at,
            version=1,
            created_at=first.received_at,
            updated_at=messages[-1].received_at,
        )
        request = CaseRequestModel(
            public_id=f"REQ-{case_public_id}",
            organization_id=organization_id,
            case_id=case_id,
            channel="email",
            customer_message=customer_message.body,
            summary=first.subject[:500],
            received_at=customer_message.received_at,
        )
        customer = CaseCustomerModel(
            organization_id=organization_id,
            case_id=case_id,
            customer_id=f"EMAIL-{sha256(customer_message.sender.address.encode()).hexdigest()[:12]}",
            name=customer_message.sender.name or customer_message.sender.address,
            tier="standard",
            locale="en",
            contact=customer_message.sender.address,
            captured_at=customer_message.received_at,
        )
        conversation = ConversationThreadModel(
            id=thread_id,
            public_id=f"CV-{case_public_id}",
            organization_id=organization_id,
            case_id=case_id,
            version=1,
            updated_at=first.received_at,
        )
        local_message = build_inbox_message(
            message_id=local_message_id,
            organization_id=organization_id,
            case_id=case_id,
            thread_id=thread_id,
            message=first,
        )
        self._session.add(case)
        self._session.flush()
        self._session.add_all([request, customer, conversation])
        self._session.flush()
        self._session.add(local_message)
        self._audit(
            case=case,
            actor_id=None,
            actor_type="system",
            event_type="case.imported",
            summary="Case imported from a connected inbox.",
            data={"source": "connected_inbox", "connection_id": connection_public_id},
            correlation_id=correlation_id,
        )
        DataGovernanceRepository(self._session).backfill(
            organization_public_id=organization_public_id,
            apply=True,
        )
        self._session.flush()
        return ImportedCaseHandle(
            case_id=case_id,
            case_public_id=case_public_id,
            thread_id=thread_id,
            first_local_message_id=local_message_id,
        )

    def append_message(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        thread_id: UUID,
        message: ProviderMessage,
        correlation_id: str,
    ) -> UUID:
        current = self._required_case(organization_public_id, case_public_id)
        case = self._session.scalar(
            select(CaseModel).where(CaseModel.id == current.id).with_for_update()
        )
        if case is None:
            raise LookupError("The case was not found.")
        thread = self._session.scalar(
            select(ConversationThreadModel)
            .where(
                ConversationThreadModel.organization_id == case.organization_id,
                ConversationThreadModel.case_id == case.id,
                ConversationThreadModel.id == thread_id,
            )
            .with_for_update()
        )
        if thread is None:
            raise LookupError("The case conversation was not found.")
        local_message_id = uuid4()
        self._session.add(
            build_inbox_message(
                message_id=local_message_id,
                organization_id=case.organization_id,
                case_id=case.id,
                thread_id=thread.id,
                message=message,
            )
        )
        case.version += 1
        case.updated_at = max(case.updated_at, message.received_at)
        case.source_checked_at = message.received_at
        case.source_freshness = "current"
        thread.version += 1
        thread.updated_at = max(thread.updated_at, message.received_at)
        self._audit(
            case=case,
            actor_id=None,
            actor_type="system",
            event_type="case.inbox_message_imported",
            summary="New inbox message added to the conversation.",
            data={
                "direction": message.direction.value,
                "case_completed": case.status == "completed",
            },
            correlation_id=correlation_id,
        )
        self._session.flush()
        return local_message_id
