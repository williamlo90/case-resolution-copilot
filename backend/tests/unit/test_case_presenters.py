from app.api.presenters.cases import present_case_queue_summary
from app.api.schemas.cases import CaseQueueSummaryResponse
from app.domain.cases import CaseQueueSummaryRecord


def test_case_queue_summary_crosses_the_api_boundary_explicitly() -> None:
    record = CaseQueueSummaryRecord(
        total=12,
        attention=5,
        review=3,
        sla_at_risk=2,
        unassigned=4,
    )

    response = present_case_queue_summary(record)

    assert isinstance(response, CaseQueueSummaryResponse)
    assert response.model_dump() == {
        "total": 12,
        "attention": 5,
        "review": 3,
        "sla_at_risk": 2,
        "unassigned": 4,
    }
