from pydantic import Field

from app.api.schemas.common import (
    ActorSummaryResponse,
    ApiSchema,
    DataResponse,
    PublicId,
    UtcDateTime,
    Version,
)
from app.domain.quality import (
    QualityCategory,
    QualityProjectionSource,
    QualityResult,
)


class QualityMetricResponse(ApiSchema):
    key: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    value: int | float
    unit: str = Field(min_length=1, max_length=32)
    numerator: int | None
    denominator: int | None
    status: str = Field(min_length=1, max_length=32)
    filtered_case_ids: list[PublicId]


class QualityOperationalResponse(ApiSchema):
    open_cases: int = Field(ge=0)
    cases_waiting_for_review: int = Field(ge=0)
    actions_completed: int = Field(ge=0)
    actions_failed_safe: int = Field(ge=0)
    actions_outcome_unknown: int = Field(ge=0)
    reopened_cases: int | None = Field(default=None, ge=0)


class QualityEvidenceResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    case_id: PublicId
    category: QualityCategory
    scenario: str = Field(min_length=1, max_length=300)
    expected_decision: str = Field(min_length=1, max_length=300)
    observed_decision: str = Field(min_length=1, max_length=300)
    policy_evidence: str = Field(min_length=1, max_length=1000)
    policy_evidence_present: bool
    customer_or_business_impact: str | None = Field(default=None, max_length=1000)
    result: QualityResult
    evaluated_by: ActorSummaryResponse
    source: QualityProjectionSource
    version: Version
    evaluated_at: UtcDateTime


class QualityDashboardResponse(ApiSchema):
    organization_id: PublicId
    metrics: list[QualityMetricResponse]
    operational: QualityOperationalResponse
    evidence: list[QualityEvidenceResponse]
    available_categories: list[QualityCategory]
    generated_at: UtcDateTime
    source_updated_at: UtcDateTime | None
    total: int = Field(ge=0)


class QualityDashboardEnvelope(DataResponse[QualityDashboardResponse]):
    pass


class CaseQualityResponse(ApiSchema):
    organization_id: PublicId
    case_id: PublicId
    evidence: list[QualityEvidenceResponse]


class CaseQualityEnvelope(DataResponse[CaseQualityResponse]):
    pass
