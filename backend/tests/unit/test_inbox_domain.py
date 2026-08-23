from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.inbox import (
    DraftLookupResult,
    DraftLookupStatus,
    DraftReceipt,
)


def _receipt() -> DraftReceipt:
    return DraftReceipt(
        provider_draft_id="draft-1",
        provider_message_id="message-1",
        provider_thread_id="thread-1",
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
    )


def test_draft_lookup_rejects_impossible_states() -> None:
    with pytest.raises(ValidationError):
        DraftLookupResult(status=DraftLookupStatus.FOUND)
    with pytest.raises(ValidationError):
        DraftLookupResult(status=DraftLookupStatus.ABSENT, receipt=_receipt())
    with pytest.raises(ValidationError):
        DraftLookupResult(
            status=DraftLookupStatus.AMBIGUOUS,
            absence_is_terminal=True,
        )


def test_terminal_absence_is_explicit() -> None:
    result = DraftLookupResult(
        status=DraftLookupStatus.ABSENT,
        absence_is_terminal=True,
    )

    assert result.receipt is None
    assert result.absence_is_terminal is True
