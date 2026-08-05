from app.domain.cases import CaseCategory, SourceFreshness
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator


def test_simulator_covers_three_generic_case_templates() -> None:
    cases = DeterministicCaseSourceSimulator().fetch_cases()

    assert len(cases) == 3
    assert {case.category for case in cases} == {
        CaseCategory.BILLING_DISPUTE,
        CaseCategory.REFUND_REQUEST,
        CaseCategory.ACCOUNT_ACCESS,
    }
    assert all(case.business_contexts for case in cases)
    assert {case.source_freshness for case in cases} >= {
        SourceFreshness.CURRENT,
        SourceFreshness.STALE,
    }


def test_simulator_payload_has_no_travel_specific_required_shape() -> None:
    payload = " ".join(
        case.model_dump_json().lower() for case in DeterministicCaseSourceSimulator().fetch_cases()
    )

    assert "booking" not in payload
    assert "flight" not in payload
    assert "passenger" not in payload
