import pytest
from pydantic import ValidationError

from app.domain.cases import (
    CASE_TRANSITIONS,
    BusinessEvidenceCreate,
    BusinessObjectType,
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


def test_verified_evidence_normalizes_safe_structured_fields() -> None:
    evidence = BusinessEvidenceCreate(
        type=BusinessObjectType.PAYMENT,
        label=" Second charge ",
        source=" Billing system ",
        source_reference=" PAY-2 ",
        status=" settled ",
        fields={" Amount ": " 49.00 ", "currency": " USD "},
    )

    assert evidence.label == "Second charge"
    assert evidence.source_reference == "PAY-2"
    assert evidence.fields == {"amount": "49.00", "currency": "USD"}


def test_verified_evidence_rejects_unstructured_or_empty_fields() -> None:
    with pytest.raises(ValidationError):
        BusinessEvidenceCreate(
            type=BusinessObjectType.PAYMENT,
            label="Second charge",
            source="Billing system",
            source_reference="PAY-2",
            status="settled",
            fields={"card number": ""},
        )
