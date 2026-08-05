from app.domain.cases import (
    CASE_TRANSITIONS,
    CaseStatus,
    InvalidCaseTransition,
    require_case_transition,
)


def test_all_active_case_states_have_explicit_transitions() -> None:
    assert set(CASE_TRANSITIONS) == set(CaseStatus)
    assert CASE_TRANSITIONS[CaseStatus.COMPLETED] == frozenset()


def test_valid_case_transition_is_accepted() -> None:
    require_case_transition(CaseStatus.NEW, CaseStatus.INVESTIGATING)


def test_invalid_case_transition_is_rejected() -> None:
    try:
        require_case_transition(CaseStatus.NEW, CaseStatus.COMPLETED)
    except InvalidCaseTransition as exc:
        assert "new" in str(exc)
        assert "completed" in str(exc)
    else:
        raise AssertionError("Invalid transition was accepted.")
