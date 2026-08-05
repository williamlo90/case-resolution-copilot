from typing import Literal

from pydantic import Field

from app.api.schemas.common import (
    ApiSchema,
    CursorPage,
    DataResponse,
    PublicId,
    UtcDateTime,
    Version,
)
from app.domain.cases import MessageAuthorType


class ConversationMessageResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    case_id: PublicId
    author_type: MessageAuthorType
    author_id: PublicId | None
    author_name: str = Field(min_length=1, max_length=200)
    channel: Literal["email", "chat", "phone", "webhook", "internal_note"]
    body: str = Field(min_length=1)
    internal: bool
    source_reference: str | None = Field(default=None, max_length=200)
    created_at: UtcDateTime
    version: Version


class ConversationThreadResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    case_id: PublicId
    messages: list[ConversationMessageResponse]
    version: Version
    updated_at: UtcDateTime


class SaveDraftRequest(ApiSchema):
    expected_version: int = Field(ge=0)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)


class AddConversationMessageRequest(ApiSchema):
    expected_case_version: Version
    channel: Literal["email", "chat", "phone", "internal_note"]
    body: str = Field(min_length=1)


class AddInternalNoteRequest(ApiSchema):
    expected_case_version: Version
    body: str = Field(min_length=1)


class ConversationDetailResponse(DataResponse[ConversationThreadResponse]):
    pass


class ConversationMessagePageResponse(CursorPage[ConversationMessageResponse]):
    pass
