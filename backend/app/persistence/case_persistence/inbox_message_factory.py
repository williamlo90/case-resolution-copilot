from uuid import UUID, uuid4

from app.domain.cases import MessageAuthorType
from app.domain.inbox import MessageDirection, ProviderMessage
from app.persistence.models import ConversationMessageModel


def build_inbox_message(
    *,
    message_id: UUID,
    organization_id: UUID,
    case_id: UUID,
    thread_id: UUID,
    message: ProviderMessage,
) -> ConversationMessageModel:
    inbound = message.direction is MessageDirection.INBOUND
    return ConversationMessageModel(
        id=message_id,
        public_id=f"MSG-{uuid4().hex[:12].upper()}",
        organization_id=organization_id,
        case_id=case_id,
        thread_id=thread_id,
        author_type=(
            MessageAuthorType.CUSTOMER.value if inbound else MessageAuthorType.SYSTEM.value
        ),
        author_id=None,
        author_name=message.sender.name or message.sender.address,
        channel="email",
        body=message.body,
        internal=False,
        source_reference=message.provider_message_id,
        version=1,
        created_at=message.received_at,
    )
