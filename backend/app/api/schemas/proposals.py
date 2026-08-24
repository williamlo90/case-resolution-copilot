from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.api.schemas.common import ApiSchema, MoneyResponse, PublicId, UtcDateTime, Version


class ProposalState(StrEnum):
    DRAFT = "draft"
    INFORMATION_NEEDED = "information_needed"
    READY_FOR_REVIEW = "ready_for_review"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProposalSummaryResponse(ApiSchema):
    id: PublicId
    version: Version
    outcome: str = Field(min_length=1, max_length=500)


class ProposedActionResponse(ApiSchema):
    id: PublicId
    type: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=300)
    impact: MoneyResponse | None
    expected_outcome: str = Field(min_length=1)
    review_required: bool


class ResponseDraftResponse(ApiSchema):
    id: PublicId
    version: Version
    source: Literal["suggested", "saved", "placeholder"]
    edit_version: int = Field(ge=0)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)
    status: Literal["draft", "ready", "blocked"]
    updated_at: UtcDateTime


class ProposalResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    case_id: PublicId
    version: Version
    outcome: str = Field(min_length=1, max_length=500)
    impact: MoneyResponse | None
    confidence: Literal["high", "medium", "low"]
    uncertainty: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    state: ProposalState
    evidence_ids: list[PublicId]
    context_snapshot_ids: list[PublicId]
    risk_rule_version: str = Field(min_length=1, max_length=100)
    model_version: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)
    graph_version: str = Field(min_length=1, max_length=100)
    created_at: UtcDateTime


class ProposalDetailResponse(ApiSchema):
    proposal: ProposalResponse
    proposed_actions: list[ProposedActionResponse]
    response_draft: ResponseDraftResponse
