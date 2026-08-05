from datetime import UTC, datetime

import pytest

from app.domain.cases import CaseHistoryPosition
from app.services.case_history_service import (
    CaseHistoryKind,
    InvalidCaseHistoryCursor,
    decode_case_history_cursor,
    encode_case_history_cursor,
)

POSITION = CaseHistoryPosition(
    occurred_at=datetime(2026, 7, 30, 8, 0, tzinfo=UTC),
    tie_breaker="MSG-0001",
)


def test_case_history_cursor_round_trips_for_one_case_section() -> None:
    cursor = encode_case_history_cursor(
        POSITION,
        kind="conversation",
        case_id="CS-2048",
    )

    assert cursor is not None
    assert (
        decode_case_history_cursor(
            cursor,
            kind="conversation",
            case_id="CS-2048",
        )
        == POSITION
    )


@pytest.mark.parametrize(
    ("kind", "case_id"),
    [
        ("activity", "CS-2048"),
        ("conversation", "CS-2047"),
    ],
)
def test_case_history_cursor_cannot_cross_case_or_section(
    kind: CaseHistoryKind,
    case_id: str,
) -> None:
    cursor = encode_case_history_cursor(
        POSITION,
        kind="conversation",
        case_id="CS-2048",
    )

    with pytest.raises(InvalidCaseHistoryCursor, match="does not match"):
        decode_case_history_cursor(
            cursor,
            kind=kind,
            case_id=case_id,
        )


def test_case_activity_cursor_requires_a_uuid_tie_breaker() -> None:
    cursor = encode_case_history_cursor(
        POSITION,
        kind="activity",
        case_id="CS-2048",
    )

    with pytest.raises(InvalidCaseHistoryCursor, match="activity cursor"):
        decode_case_history_cursor(
            cursor,
            kind="activity",
            case_id="CS-2048",
        )
