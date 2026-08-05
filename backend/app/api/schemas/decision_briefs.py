from pydantic import Field

from app.api.schemas.cases import (
    MissingInformationResponse,
    RiskCheckResponse,
    VerifiedFactResponse,
)
from app.api.schemas.common import ApiSchema, DataResponse, PublicId, UtcDateTime, Version
from app.api.schemas.proposals import (
    ProposalResponse,
    ProposedActionResponse,
    ResponseDraftResponse,
)
from app.domain.decision_briefs import AnalysisStatus, CheckpointStatus
from app.domain.policies import EvidenceRetrievalStatus


class GenerateDecisionBriefRequest(ApiSchema):
    expected_case_version: Version


class AnalysisRunResponse(ApiSchema):
    id: PublicId
    case_id: PublicId
    status: AnalysisStatus
    policy_status: EvidenceRetrievalStatus
    case_version: Version
    initiated_by: PublicId
    model_version: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=100)
    graph_version: str = Field(min_length=1, max_length=100)
    risk_rule_version: str = Field(min_length=1, max_length=100)
    completed_at: UtcDateTime


class AnalysisCheckpointResponse(ApiSchema):
    id: PublicId
    sequence: int = Field(ge=1)
    step: str = Field(min_length=1, max_length=64)
    status: CheckpointStatus
    summary: str = Field(min_length=1, max_length=1000)
    created_at: UtcDateTime


class DecisionBriefResponse(ApiSchema):
    analysis: AnalysisRunResponse
    facts: list[VerifiedFactResponse]
    missing_information: list[MissingInformationResponse]
    risks: list[RiskCheckResponse]
    proposal: ProposalResponse
    proposed_actions: list[ProposedActionResponse]
    response_draft: ResponseDraftResponse
    checkpoints: list[AnalysisCheckpointResponse]


class DecisionBriefEnvelope(DataResponse[DecisionBriefResponse]):
    pass
