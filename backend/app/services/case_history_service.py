import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.domain.cases import (
    CaseActivityPageRecord,
    CaseActivityRecord,
    CaseHistoryPosition,
    ConversationMessagePageRecord,
    ConversationMessageRecord,
)
from app.domain.identity import ActorContext, Permission
from app.security.authorization import require_permission

CaseHistoryKind = Literal["conversation", "activity"]


class InvalidCaseHistoryCursor(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CaseHistoryPage[ItemT]:
    items: tuple[ItemT, ...]
    next_cursor: str | None
    total: int


class CaseHistoryStore(Protocol):
    def list_conversation_messages(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        before: CaseHistoryPosition | None,
        limit: int,
    ) -> ConversationMessagePageRecord: ...

    def list_case_activity(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        before: CaseHistoryPosition | None,
        limit: int,
    ) -> CaseActivityPageRecord: ...


class _CursorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CaseHistoryKind
    case_id: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    tie_breaker: str = Field(min_length=1, max_length=128)

    @field_validator("occurred_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("cursor timestamp must be timezone-aware UTC")
        return value


class CaseHistoryService:
    def __init__(self, store: CaseHistoryStore) -> None:
        self._store = store

    def conversation(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        cursor: str | None,
        limit: int,
    ) -> CaseHistoryPage[ConversationMessageRecord]:
        require_permission(actor, Permission.CASE_READ)
        page = self._store.list_conversation_messages(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            before=decode_case_history_cursor(
                cursor,
                kind="conversation",
                case_id=case_id,
            ),
            limit=limit,
        )
        return CaseHistoryPage(
            items=tuple(page.items),
            next_cursor=encode_case_history_cursor(
                page.next_position,
                kind="conversation",
                case_id=case_id,
            ),
            total=page.total,
        )

    def activity(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        cursor: str | None,
        limit: int,
    ) -> CaseHistoryPage[CaseActivityRecord]:
        require_permission(actor, Permission.CASE_READ)
        page = self._store.list_case_activity(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            before=decode_case_history_cursor(
                cursor,
                kind="activity",
                case_id=case_id,
            ),
            limit=limit,
        )
        return CaseHistoryPage(
            items=tuple(page.items),
            next_cursor=encode_case_history_cursor(
                page.next_position,
                kind="activity",
                case_id=case_id,
            ),
            total=page.total,
        )


def encode_case_history_cursor(
    position: CaseHistoryPosition | None,
    *,
    kind: CaseHistoryKind,
    case_id: str,
) -> str | None:
    if position is None:
        return None
    payload = _CursorPayload(
        kind=kind,
        case_id=case_id,
        occurred_at=position.occurred_at,
        tie_breaker=position.tie_breaker,
    )
    encoded = json.dumps(payload.model_dump(mode="json"), separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(encoded).decode().rstrip("=")


def decode_case_history_cursor(
    cursor: str | None,
    *,
    kind: CaseHistoryKind,
    case_id: str,
) -> CaseHistoryPosition | None:
    if cursor is None:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        raw_payload = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = _CursorPayload.model_validate_json(raw_payload)
    except (
        binascii.Error,
        UnicodeDecodeError,
        ValidationError,
        ValueError,
    ) as error:
        raise InvalidCaseHistoryCursor("The case history cursor is invalid.") from error
    if payload.kind != kind or payload.case_id != case_id:
        raise InvalidCaseHistoryCursor(
            "The case history cursor does not match this case and section."
        )
    if kind == "activity":
        try:
            UUID(payload.tie_breaker)
        except ValueError as error:
            raise InvalidCaseHistoryCursor(
                "The case activity cursor is invalid."
            ) from error
    return CaseHistoryPosition(
        occurred_at=payload.occurred_at,
        tie_breaker=payload.tie_breaker,
    )
