from app.domain.actions import (
    ManualActionOutcome,
    ReconciliationOutcome,
    reconciliation_outcome_for_lookup,
    reconciliation_outcome_for_manual_record,
)


def test_eventually_consistent_lookup_misses_never_unlock_retry() -> None:
    observations = [False, False, True]

    outcomes = [
        reconciliation_outcome_for_lookup(
            found=found,
            absence_is_terminal=False,
        )
        for found in observations
    ]

    assert outcomes == [
        ReconciliationOutcome.STILL_UNKNOWN,
        ReconciliationOutcome.STILL_UNKNOWN,
        ReconciliationOutcome.CONFIRMED_COMPLETED,
    ]
    assert ReconciliationOutcome.CONFIRMED_ABSENT not in outcomes


def test_only_explicit_terminal_absence_can_unlock_a_safe_retry() -> None:
    assert reconciliation_outcome_for_lookup(
        found=False,
        absence_is_terminal=True,
    ) is ReconciliationOutcome.CONFIRMED_ABSENT


def test_manual_not_completed_note_keeps_the_outcome_unknown() -> None:
    assert reconciliation_outcome_for_manual_record(
        ManualActionOutcome.NOT_COMPLETED
    ) is ReconciliationOutcome.STILL_UNKNOWN
