import base64
import binascii
import hashlib
import json
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.cases import (
    BusinessEvidenceCreate,
    BusinessEvidenceNotAllowed,
    CaseCategory,
    CaseListPageRecord,
    CaseNotFound,
    CaseQueueCursorRecord,
    CaseQueueSort,
    CaseQueueView,
    CaseStatus,
    CaseWorkspaceRecord,
    MessageChannel,
    require_case_transition,
)
from app.domain.identity import ActorContext, Permission
from app.security.authorization import require_permission


class InvalidCaseCursor(ValueError):
    pass


class CaseStore(Protocol):
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
    ) -> CaseListPageRecord: ...

    def get_workspace(
        self, *, organization_public_id: str, case_public_id: str
    ) -> CaseWorkspaceRecord | None: ...

    def assign_to_actor(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_version: int,
        correlation_id: str,
    ) -> CaseWorkspaceRecord: ...

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
    ) -> CaseWorkspaceRecord: ...

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
    ) -> CaseWorkspaceRecord: ...

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
    ) -> CaseWorkspaceRecord: ...

    def add_business_evidence(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        expected_case_version: int,
        evidence: BusinessEvidenceCreate,
        correlation_id: str,
    ) -> CaseWorkspaceRecord: ...


class CaseService:
    def __init__(self, store: CaseStore) -> None:
        self._store = store

    def list_cases(
        self,
        *,
        actor: ActorContext,
        status: CaseStatus | None,
        category: CaseCategory | None,
        query: str | None,
        cursor: str | None,
        limit: int,
        view: CaseQueueView = CaseQueueView.ALL,
        sort: CaseQueueSort = CaseQueueSort.PRIORITY,
    ) -> CaseListPageRecord:
        require_permission(actor, Permission.CASE_READ)
        return self._store.list_cases(
            organization_public_id=actor.organization_id,
            status=status,
            category=category,
            query=query,
            cursor=decode_cursor(
                cursor,
                status=status,
                category=category,
                query=query,
                view=view,
                sort=sort,
            ),
            limit=limit,
            actor_public_id=actor.actor_id,
            view=view,
            sort=sort,
        )

    def get_case(self, *, actor: ActorContext, case_id: str) -> CaseWorkspaceRecord:
        require_permission(actor, Permission.CASE_READ)
        workspace = self._store.get_workspace(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )
        if workspace is None:
            raise CaseNotFound("The case was not found.")
        return workspace

    def assign_to_me(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        require_permission(actor, Permission.CASE_MANAGE)
        return self._store.assign_to_actor(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_version=expected_version,
            correlation_id=correlation_id,
        )

    def change_status(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_version: int,
        target: CaseStatus,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        require_permission(actor, Permission.CASE_MANAGE)
        current = self.get_case(actor=actor, case_id=case_id)
        require_case_transition(current.case.status, target)
        return self._store.change_status(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_version=expected_version,
            target=target,
            correlation_id=correlation_id,
        )

    def add_message(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_case_version: int,
        channel: MessageChannel,
        body: str,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        require_permission(actor, Permission.CASE_MANAGE)
        return self._store.add_message(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            actor_name=actor.name,
            actor_type=actor.kind.value,
            expected_case_version=expected_case_version,
            channel=channel,
            body=body,
            correlation_id=correlation_id,
        )

    def save_draft(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_version: int,
        subject: str,
        body: str,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        require_permission(actor, Permission.CASE_MANAGE)
        return self._store.save_draft(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_version=expected_version,
            subject=subject,
            body=body,
            correlation_id=correlation_id,
        )

    def add_business_evidence(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_case_version: int,
        evidence: BusinessEvidenceCreate,
        correlation_id: str,
    ) -> CaseWorkspaceRecord:
        require_permission(actor, Permission.CASE_MANAGE)
        current = self.get_case(actor=actor, case_id=case_id)
        if current.case.status is CaseStatus.COMPLETED:
            raise BusinessEvidenceNotAllowed(
                "Reopen the case before adding a verified record."
            )
        return self._store.add_business_evidence(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            expected_case_version=expected_case_version,
            evidence=evidence,
            correlation_id=correlation_id,
        )


class _CaseCursorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[2] = 2
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    cursor: CaseQueueCursorRecord


def encode_cursor(
    cursor: CaseQueueCursorRecord | None,
    *,
    status: CaseStatus | None = None,
    category: CaseCategory | None = None,
    query: str | None = None,
    view: CaseQueueView = CaseQueueView.ALL,
    sort: CaseQueueSort = CaseQueueSort.PRIORITY,
) -> str | None:
    if cursor is None:
        return None
    _validate_cursor_position(cursor, sort=sort)
    payload = _CaseCursorPayload(
        context_hash=_cursor_context_hash(
            status=status,
            category=category,
            query=query,
            view=view,
            sort=sort,
        ),
        cursor=cursor,
    )
    encoded = json.dumps(
        payload.model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(encoded).decode().rstrip("=")


def decode_cursor(
    cursor: str | None,
    *,
    status: CaseStatus | None = None,
    category: CaseCategory | None = None,
    query: str | None = None,
    view: CaseQueueView = CaseQueueView.ALL,
    sort: CaseQueueSort = CaseQueueSort.PRIORITY,
) -> CaseQueueCursorRecord | None:
    if cursor is None:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        raw_payload = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = _CaseCursorPayload.model_validate_json(raw_payload)
        if payload.context_hash != _cursor_context_hash(
            status=status,
            category=category,
            query=query,
            view=view,
            sort=sort,
        ):
            raise ValueError("Cursor filters do not match the request.")
        _validate_cursor_position(payload.cursor, sort=sort)
    except (
        binascii.Error,
        UnicodeDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
        raise InvalidCaseCursor("The case cursor is invalid.") from exc
    return payload.cursor


def _cursor_context_hash(
    *,
    status: CaseStatus | None,
    category: CaseCategory | None,
    query: str | None,
    view: CaseQueueView,
    sort: CaseQueueSort,
) -> str:
    context = {
        "status": status.value if status is not None else None,
        "category": category.value if category is not None else None,
        "query": query.strip() if query is not None else None,
        "view": view.value,
        "sort": sort.value,
    }
    canonical = json.dumps(context, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


def _validate_cursor_position(
    cursor: CaseQueueCursorRecord,
    *,
    sort: CaseQueueSort,
) -> None:
    if sort is CaseQueueSort.PRIORITY and cursor.position.risk_rank is None:
        raise ValueError("Priority cursors require a risk rank.")
    if sort is not CaseQueueSort.PRIORITY and cursor.position.risk_rank is not None:
        raise ValueError("Only priority cursors may include a risk rank.")
