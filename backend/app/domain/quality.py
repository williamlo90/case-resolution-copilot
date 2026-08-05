from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QualityCategory(StrEnum):
    DECISION_QUALITY = "decision_quality"
    SAFETY = "safety"
    RELIABILITY = "reliability"


class QualityResult(StrEnum):
    PASSED = "passed"
    NEEDS_ATTENTION = "needs_attention"


class QualityProjectionSource(StrEnum):
    DETERMINISTIC_DEMO = "deterministic_demo"
    MANUAL = "manual"
    IMPORTED = "imported"


class CaseQualityProjectionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    case_public_id: str
    category: QualityCategory
    scenario: str
    expected_decision: str
    observed_decision: str
    policy_evidence: str
    policy_evidence_present: bool
    customer_or_business_impact: str | None
    result: QualityResult
    evaluated_by_id: UUID
    evaluated_by_public_id: str
    evaluated_by_name: str
    source: QualityProjectionSource
    source_fingerprint: str
    version: int = Field(ge=1)
    evaluated_at: datetime
    updated_at: datetime


class QualityMetricRecord(BaseModel):
    key: str
    label: str
    value: int | float
    unit: str
    numerator: int | None = None
    denominator: int | None = None
    status: str
    filtered_case_ids: list[str]


class QualityOperationalSummary(BaseModel):
    open_cases: int
    cases_waiting_for_review: int
    actions_completed: int
    actions_failed_safe: int
    actions_outcome_unknown: int
    reopened_cases: int | None


class QualityDashboardRecord(BaseModel):
    metrics: list[QualityMetricRecord]
    operational: QualityOperationalSummary
    evidence: list[CaseQualityProjectionRecord]
    available_categories: list[QualityCategory]
    generated_at: datetime
    source_updated_at: datetime | None
    total: int


class QualityProjectionSeed(BaseModel):
    case_public_id: str = Field(min_length=1, max_length=64)
    category: QualityCategory
    scenario: str = Field(min_length=1, max_length=300)
    expected_decision: str = Field(min_length=1, max_length=300)
    observed_decision: str = Field(min_length=1, max_length=300)
    policy_evidence: str = Field(min_length=1, max_length=1000)
    policy_evidence_present: bool
    customer_or_business_impact: str | None = Field(default=None, max_length=1000)
    result: QualityResult
    evaluated_by_public_id: str = Field(min_length=1, max_length=64)
    source: QualityProjectionSource
    evaluated_at: datetime


class QualityProjectionNotFound(LookupError):
    pass


class QualityConflict(RuntimeError):
    pass
