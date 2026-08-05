from app.api.schemas.common import ActorSummaryResponse
from app.api.schemas.quality import (
    QualityDashboardResponse,
    QualityEvidenceResponse,
    QualityMetricResponse,
    QualityOperationalResponse,
)
from app.domain.quality import (
    CaseQualityProjectionRecord,
    QualityDashboardRecord,
)


def present_quality_evidence(
    record: CaseQualityProjectionRecord,
    *,
    organization_id: str,
) -> QualityEvidenceResponse:
    return QualityEvidenceResponse(
        id=record.public_id,
        organization_id=organization_id,
        case_id=record.case_public_id,
        category=record.category,
        scenario=record.scenario,
        expected_decision=record.expected_decision,
        observed_decision=record.observed_decision,
        policy_evidence=record.policy_evidence,
        policy_evidence_present=record.policy_evidence_present,
        customer_or_business_impact=record.customer_or_business_impact,
        result=record.result,
        evaluated_by=ActorSummaryResponse(
            id=record.evaluated_by_public_id,
            name=record.evaluated_by_name,
        ),
        source=record.source,
        version=record.version,
        evaluated_at=record.evaluated_at,
    )


def present_quality_dashboard(
    record: QualityDashboardRecord,
    *,
    organization_id: str,
) -> QualityDashboardResponse:
    return QualityDashboardResponse(
        organization_id=organization_id,
        metrics=[
            QualityMetricResponse(
                key=metric.key,
                label=metric.label,
                value=metric.value,
                unit=metric.unit,
                numerator=metric.numerator,
                denominator=metric.denominator,
                status=metric.status,
                filtered_case_ids=metric.filtered_case_ids,
            )
            for metric in record.metrics
        ],
        operational=QualityOperationalResponse(
            open_cases=record.operational.open_cases,
            cases_waiting_for_review=record.operational.cases_waiting_for_review,
            actions_completed=record.operational.actions_completed,
            actions_failed_safe=record.operational.actions_failed_safe,
            actions_outcome_unknown=record.operational.actions_outcome_unknown,
            reopened_cases=record.operational.reopened_cases,
        ),
        evidence=[
            present_quality_evidence(item, organization_id=organization_id)
            for item in record.evidence
        ],
        available_categories=record.available_categories,
        generated_at=record.generated_at,
        source_updated_at=record.source_updated_at,
        total=record.total,
    )
