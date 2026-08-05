from datetime import UTC, datetime
from typing import cast

import pytest

from app.domain.cases import (
    CaseCategory,
    CaseListPageRecord,
    CaseQueueCursorDirection,
    CaseQueueCursorRecord,
    CaseQueuePosition,
    CaseQueueSort,
    CaseQueueView,
    CaseStatus,
    CaseWorkspaceRecord,
    InvalidCaseTransition,
)
from app.security.authentication import DeterministicAuthProvider
from app.security.authorization import PermissionDenied
from app.services.case_service import (
    CaseService,
    CaseStore,
    InvalidCaseCursor,
    decode_cursor,
    encode_cursor,
)
from tests.builders import valid_case_workspace

SNAPSHOT_AT = datetime(2026, 7, 30, 10, 5, tzinfo=UTC)


class RecordingCaseStore:
    def __init__(self) -> None:
        self.organization_ids: list[str] = []
        self.list_values: list[dict[str, object]] = []
        self.change_called = False

    def list_cases(self, **values: object) -> CaseListPageRecord:
        self.organization_ids.append(str(values["organization_public_id"]))
        self.list_values.append(values)
        return CaseListPageRecord(
            items=[],
            next_cursor=None,
            previous_cursor=None,
            total=0,
        )

    def get_workspace(self, **values: object) -> CaseWorkspaceRecord:
        self.organization_ids.append(str(values["organization_public_id"]))
        return valid_case_workspace()

    def change_status(self, **values: object) -> CaseWorkspaceRecord:
        self.change_called = True
        return self.get_workspace(**values)


def test_case_list_scope_always_comes_from_authenticated_actor() -> None:
    store = RecordingCaseStore()
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    CaseService(cast(CaseStore, store)).list_cases(
        actor=actor,
        status=None,
        category=None,
        query=None,
        cursor=None,
        limit=25,
    )

    assert store.organization_ids == ["ORG-0001"]


def test_case_list_passes_view_sort_and_keyset_cursor_to_the_store() -> None:
    store = RecordingCaseStore()
    actor = DeterministicAuthProvider().authenticate("USR-0001")
    decoded_cursor = CaseQueueCursorRecord(
        direction=CaseQueueCursorDirection.FORWARD,
        offset=120,
        snapshot_at=SNAPSHOT_AT,
        position=CaseQueuePosition(
            ordered_at=datetime(2026, 7, 30, 10, 0, tzinfo=UTC),
            public_id="CS-0120",
        ),
    )
    cursor = encode_cursor(
        decoded_cursor,
        query="payment",
        view=CaseQueueView.AT_RISK,
        sort=CaseQueueSort.UPDATED,
    )

    CaseService(cast(CaseStore, store)).list_cases(
        actor=actor,
        status=None,
        category=None,
        query="payment",
        cursor=cursor,
        limit=8,
        view=CaseQueueView.AT_RISK,
        sort=CaseQueueSort.UPDATED,
    )

    assert store.list_values == [
        {
            "organization_public_id": "ORG-0001",
            "status": None,
            "category": None,
            "query": "payment",
            "cursor": decoded_cursor,
            "limit": 8,
            "actor_public_id": actor.actor_id,
            "view": CaseQueueView.AT_RISK,
            "sort": CaseQueueSort.UPDATED,
        }
    ]


def test_auditor_cannot_mutate_a_case() -> None:
    store = RecordingCaseStore()
    actor = DeterministicAuthProvider().authenticate("USR-0004")

    with pytest.raises(PermissionDenied):
        CaseService(cast(CaseStore, store)).change_status(
            actor=actor,
            case_id="CS-2048",
            expected_version=1,
            target=CaseStatus.INVESTIGATING,
            correlation_id="corr-test",
        )

    assert not store.change_called


def test_invalid_transition_is_rejected_before_the_write_store() -> None:
    store = RecordingCaseStore()
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(InvalidCaseTransition):
        CaseService(cast(CaseStore, store)).change_status(
            actor=actor,
            case_id="CS-2048",
            expected_version=1,
            target=CaseStatus.COMPLETED,
            correlation_id="corr-test",
        )

    assert not store.change_called
    assert store.organization_ids == ["ORG-0001"]


def test_case_cursor_is_opaque_and_round_trips() -> None:
    decoded_cursor = CaseQueueCursorRecord(
        direction=CaseQueueCursorDirection.FORWARD,
        offset=25,
        snapshot_at=SNAPSHOT_AT,
        position=CaseQueuePosition(
            ordered_at=datetime(2026, 7, 30, 10, 0, tzinfo=UTC),
            public_id="CS-0025",
            risk_rank=1,
        ),
    )
    cursor = encode_cursor(
        decoded_cursor,
        status=CaseStatus.INVESTIGATING,
        category=CaseCategory.BILLING_DISPUTE,
        query="charge",
    )

    assert cursor is not None
    assert cursor != "25"
    assert "charge" not in cursor
    assert (
        decode_cursor(
            cursor,
            status=CaseStatus.INVESTIGATING,
            category=CaseCategory.BILLING_DISPUTE,
            query="charge",
        )
        == decoded_cursor
    )


def test_case_cursor_cannot_be_reused_with_different_filters() -> None:
    cursor = encode_cursor(
        CaseQueueCursorRecord(
            direction=CaseQueueCursorDirection.FORWARD,
            offset=25,
            snapshot_at=SNAPSHOT_AT,
            position=CaseQueuePosition(
                ordered_at=datetime(2026, 7, 30, 10, 0, tzinfo=UTC),
                public_id="CS-0025",
                risk_rank=0,
            ),
        ),
        status=CaseStatus.NEW,
    )

    with pytest.raises(InvalidCaseCursor):
        decode_cursor(cursor, status=CaseStatus.INVESTIGATING)


def test_case_cursor_cannot_be_reused_with_different_view_or_sort() -> None:
    cursor = encode_cursor(
        CaseQueueCursorRecord(
            direction=CaseQueueCursorDirection.FORWARD,
            offset=104,
            snapshot_at=SNAPSHOT_AT,
            position=CaseQueuePosition(
                ordered_at=datetime(2026, 7, 30, 10, 0, tzinfo=UTC),
                public_id="CS-0104",
                risk_rank=2,
            ),
        ),
        view=CaseQueueView.ALL,
        sort=CaseQueueSort.PRIORITY,
    )

    with pytest.raises(InvalidCaseCursor):
        decode_cursor(cursor, view=CaseQueueView.AT_RISK)
    with pytest.raises(InvalidCaseCursor):
        decode_cursor(cursor, sort=CaseQueueSort.UPDATED)


def test_priority_cursor_requires_a_risk_rank() -> None:
    cursor = CaseQueueCursorRecord(
        direction=CaseQueueCursorDirection.FORWARD,
        offset=8,
        snapshot_at=SNAPSHOT_AT,
        position=CaseQueuePosition(
            ordered_at=datetime(2026, 7, 30, 10, 0, tzinfo=UTC),
            public_id="CS-0008",
        ),
    )

    with pytest.raises(ValueError, match="risk rank"):
        encode_cursor(cursor, sort=CaseQueueSort.PRIORITY)


@pytest.mark.parametrize("cursor", ["not-base64!", "LTE=", "bm90LWEtbnVtYmVy"])
def test_invalid_case_cursor_is_rejected(cursor: str) -> None:
    with pytest.raises(InvalidCaseCursor):
        decode_cursor(cursor)
