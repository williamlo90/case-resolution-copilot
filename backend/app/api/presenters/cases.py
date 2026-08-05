from app.api.schemas.cases import CaseQueueSummaryResponse
from app.domain.cases import CaseQueueSummaryRecord


def present_case_queue_summary(
    record: CaseQueueSummaryRecord,
) -> CaseQueueSummaryResponse:
    return CaseQueueSummaryResponse(
        total=record.total,
        attention=record.attention,
        review=record.review,
        sla_at_risk=record.sla_at_risk,
        unassigned=record.unassigned,
    )
