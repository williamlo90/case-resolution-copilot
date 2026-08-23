import json
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select, text

from app.domain.inbox import (
    ExternalConversationRecord,
    ExternalMessageRecord,
    ImportedCaseHandle,
    ProviderMessage,
)
from app.persistence.models import (
    ExternalAttachmentModel,
    ExternalConversationModel,
    ExternalMessageModel,
    utc_now,
)

from ._base import InboxRepositoryBase


class InboxMessageRepository(InboxRepositoryBase):
    def lock_thread(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        provider_thread_id: str,
    ) -> None:
        digest = sha256(
            f"{organization_id}:{connection_id}:{provider_thread_id}".encode()
        ).digest()
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": int.from_bytes(digest[:8], "big", signed=True)},
        )

    def get_conversation(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        provider_thread_id: str,
    ) -> ExternalConversationRecord | None:
        model = self._session.scalar(
            select(ExternalConversationModel).where(
                ExternalConversationModel.organization_id == organization_id,
                ExternalConversationModel.connection_id == connection_id,
                ExternalConversationModel.provider_thread_id == provider_thread_id,
            )
        )
        return ExternalConversationRecord.model_validate(model) if model else None

    def create_conversation(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        case: ImportedCaseHandle,
        first_message: ProviderMessage,
    ) -> ExternalConversationRecord:
        model = ExternalConversationModel(
            public_id=f"EXT-{uuid4().hex[:12].upper()}",
            organization_id=organization_id,
            connection_id=connection_id,
            case_id=case.case_id,
            thread_id=case.thread_id,
            provider_thread_id=first_message.provider_thread_id,
            subject=first_message.subject,
            first_message_at=first_message.received_at,
            latest_message_at=first_message.received_at,
            latest_provider_message_id=first_message.provider_message_id,
            source_fingerprint=sha256(b"empty-conversation").hexdigest(),
            version=1,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self._session.add(model)
        self._session.flush()
        return ExternalConversationRecord.model_validate(model)

    def has_message(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        provider_message_id: str,
    ) -> bool:
        return (
            self._session.scalar(
                select(ExternalMessageModel.id).where(
                    ExternalMessageModel.organization_id == organization_id,
                    ExternalMessageModel.connection_id == connection_id,
                    ExternalMessageModel.provider_message_id == provider_message_id,
                )
            )
            is not None
        )

    def record_message(
        self,
        *,
        organization_id: UUID,
        connection_id: UUID,
        external_conversation_id: UUID,
        local_message_id: UUID,
        message: ProviderMessage,
    ) -> ExternalMessageRecord:
        now = utc_now()
        model = ExternalMessageModel(
            public_id=f"EXM-{uuid4().hex[:12].upper()}",
            organization_id=organization_id,
            connection_id=connection_id,
            external_conversation_id=external_conversation_id,
            conversation_message_id=local_message_id,
            provider_message_id=message.provider_message_id,
            rfc_message_id=message.rfc_message_id,
            direction=message.direction.value,
            sender=message.sender.model_dump(mode="json"),
            recipients=[item.model_dump(mode="json") for item in message.recipients],
            provider_received_at=message.received_at,
            observed_at=now,
            sanitized_content_hash=message.sanitized_content_hash,
            raw_source_hash=message.raw_source_hash,
            parser_version=message.parser_version,
            omission_reason=message.omission_reason,
            attachment_count=len(message.attachments),
            source_metadata={
                "provider_thread_id": message.provider_thread_id,
                "subject": message.subject,
            },
            created_at=now,
        )
        self._session.add(model)
        self._session.flush()
        self._session.add_all(
            [
                ExternalAttachmentModel(
                    public_id=f"EXA-{uuid4().hex[:12].upper()}",
                    organization_id=organization_id,
                    external_message_id=model.id,
                    provider_attachment_id=attachment.provider_attachment_id,
                    name=attachment.name,
                    media_type=attachment.media_type,
                    reported_size=attachment.reported_size,
                    content_status=attachment.content_status.value,
                    local_evidence_reference=None,
                    content_hash=None,
                    parser_status="metadata_only",
                    malware_scan_status="not_scanned",
                    created_at=now,
                )
                for attachment in message.attachments
            ]
        )
        return ExternalMessageRecord.model_validate(model)

    def finalize_conversation(
        self,
        *,
        conversation_id: UUID,
        subject: str,
        latest_message: ProviderMessage,
    ) -> ExternalConversationRecord:
        conversation = self._session.scalar(
            select(ExternalConversationModel)
            .where(ExternalConversationModel.id == conversation_id)
            .with_for_update()
        )
        if conversation is None:
            raise LookupError("The external conversation was not found.")
        conversation.subject = subject
        conversation.latest_message_at = max(
            conversation.latest_message_at,
            latest_message.received_at,
        )
        conversation.latest_provider_message_id = latest_message.provider_message_id
        conversation.source_fingerprint = self._fingerprint(conversation)
        conversation.version += 1
        conversation.updated_at = utc_now()
        self._session.flush()
        return ExternalConversationRecord.model_validate(conversation)

    def _fingerprint(self, conversation: ExternalConversationModel) -> str:
        rows = self._session.execute(
            select(
                ExternalMessageModel.provider_message_id,
                ExternalMessageModel.sanitized_content_hash,
                ExternalMessageModel.provider_received_at,
            )
            .where(
                ExternalMessageModel.organization_id == conversation.organization_id,
                ExternalMessageModel.external_conversation_id == conversation.id,
            )
            .order_by(
                ExternalMessageModel.provider_received_at,
                ExternalMessageModel.provider_message_id,
            )
        ).all()
        material = [
            {
                "message_id": message_id,
                "content_hash": content_hash,
                "received_at": received_at.isoformat(),
            }
            for message_id, content_hash, received_at in rows
        ]
        return sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
