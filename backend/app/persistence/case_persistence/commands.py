from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.domain.cases import (
    CaseActorNotAssignable,
    CaseNotFound,
    CaseStatus,
    CaseWorkspaceRecord,
    DraftConcurrencyConflict,
    MessageAuthorType,
    MessageChannel,
)
from app.persistence.models import (
    ConversationMessageModel,
    ConversationThreadModel,
    MembershipModel,
    ResponseDraftModel,
    utc_now,
)

from ._base import CaseRepositoryBase


class CaseCommandRepository(CaseRepositoryBase):
    def assign_to_actor(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_version: int,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        case = self._required_case(organization_public_id, case_public_id)
        member = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == case.organization_id,
                MembershipModel.status == "active",
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        )
        if member is None:
            raise CaseActorNotAssignable("The actor is not an active organization member.")
        updated = self._update_case(
            case=case,
            expected_version=expected_version,
            values={"owner_id": member.id},
        )
        self._audit(
            case=updated,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="case.assigned",
            summary=f"Case assigned to {member.name}.",
            data={"owner_id": member.public_id},
            correlation_id=correlation_id,
        )
        return self._required_workspace(organization_public_id, case_public_id)

    def change_status(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_version: int,
        target: CaseStatus,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        case = self._required_case(organization_public_id, case_public_id)
        previous_status = case.status
        updated = self._update_case(
            case=case,
            expected_version=expected_version,
            values={"status": target.value},
        )
        self._audit(
            case=updated,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="case.status_changed",
            summary=f"Case moved from {previous_status} to {target.value}.",
            data={"from": previous_status, "to": target.value},
            correlation_id=correlation_id,
        )
        return self._required_workspace(organization_public_id, case_public_id)

    def add_message(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_name: str,
        actor_type: str,
        expected_case_version: int,
        channel: MessageChannel,
        body: str,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        case = self._required_case(organization_public_id, case_public_id)
        updated = self._update_case(
            case=case,
            expected_version=expected_case_version,
            values={},
        )
        thread = self._session.scalar(
            select(ConversationThreadModel).where(
                ConversationThreadModel.organization_id == case.organization_id,
                ConversationThreadModel.case_id == case.id,
            )
        )
        if thread is None:
            raise CaseNotFound("The case conversation was not found.")
        now = utc_now()
        thread.version += 1
        thread.updated_at = now
        internal = channel is MessageChannel.INTERNAL_NOTE
        message = ConversationMessageModel(
            public_id=f"MSG-{uuid4().hex[:12].upper()}",
            organization_id=case.organization_id,
            case_id=case.id,
            thread_id=thread.id,
            author_type=(
                MessageAuthorType.MEMBER.value
                if actor_type == "member"
                else MessageAuthorType.SYSTEM.value
            ),
            author_id=actor_id,
            author_name=actor_name,
            channel=channel.value,
            body=body,
            internal=internal,
            source_reference=None,
            version=1,
            created_at=now,
        )
        self._session.add(message)
        self._audit(
            case=updated,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="case.note_added" if internal else "case.message_added",
            summary="Internal note added." if internal else "Conversation message added.",
            data={"channel": channel.value, "internal": internal},
            correlation_id=correlation_id,
        )
        self._session.flush()
        return self._required_workspace(organization_public_id, case_public_id)

    def save_draft(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_version: int,
        subject: str,
        body: str,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        case = self._required_case(organization_public_id, case_public_id)
        current_draft = self._session.scalar(
            select(ResponseDraftModel).where(
                ResponseDraftModel.organization_id == case.organization_id,
                ResponseDraftModel.case_id == case.id,
            )
        )
        now = utc_now()
        if current_draft is None:
            if expected_version != 0:
                raise DraftConcurrencyConflict(
                    expected_version=expected_version,
                    current_version=0,
                )
            draft = self._session.scalar(
                insert(ResponseDraftModel)
                .values(
                    public_id=f"DFT-{uuid4().hex[:12].upper()}",
                    organization_id=case.organization_id,
                    case_id=case.id,
                    subject=subject,
                    body=body,
                    status="draft",
                    version=1,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["organization_id", "case_id"])
                .returning(ResponseDraftModel)
            )
            if draft is None:
                concurrent_version = self._session.scalar(
                    select(ResponseDraftModel.version).where(
                        ResponseDraftModel.organization_id == case.organization_id,
                        ResponseDraftModel.case_id == case.id,
                    )
                )
                raise DraftConcurrencyConflict(
                    expected_version=expected_version,
                    current_version=concurrent_version or 1,
                )
        else:
            draft = self._session.scalar(
                update(ResponseDraftModel)
                .where(
                    ResponseDraftModel.id == current_draft.id,
                    ResponseDraftModel.organization_id == case.organization_id,
                    ResponseDraftModel.version == expected_version,
                )
                .values(
                    subject=subject,
                    body=body,
                    status="draft",
                    version=ResponseDraftModel.version + 1,
                    updated_at=now,
                )
                .returning(ResponseDraftModel)
            )
            if draft is None:
                current_version = self._session.scalar(
                    select(ResponseDraftModel.version).where(
                        ResponseDraftModel.id == current_draft.id,
                        ResponseDraftModel.organization_id == case.organization_id,
                    )
                )
                if current_version is None:
                    raise CaseNotFound("The response draft was not found.")
                raise DraftConcurrencyConflict(
                    expected_version=expected_version,
                    current_version=current_version,
                )
        self._audit(
            case=case,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type="case.draft_saved",
            summary="Response draft saved.",
            data={"draft_version": draft.version},
            correlation_id=correlation_id,
        )
        self._session.flush()
        return self._required_workspace(organization_public_id, case_public_id)
