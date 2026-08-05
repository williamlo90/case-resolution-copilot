from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProposalStatus(StrEnum):
    DRAFT_WAITING_EVIDENCE = "draft_waiting_evidence"
    WAITING_APPROVAL = "waiting_approval"


class IntentClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["support_escalation"]
    case_category: Literal[
        "billing",
        "account_access",
        "cancellation",
        "service_complaint",
        "privacy",
        "unknown",
    ]
    confidence: float = Field(ge=0, le=1)


class RiskDecisionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    requires_approval: bool
    risk_codes: list[str]
    explanation: str
    rule_version: str
    created_at: datetime


class ProposalVersionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    run_id: UUID
    version: int
    status: ProposalStatus
    tool_name: str
    proposal_type: str
    proposed_outcome: str
    action_type: str
    rationale: str
    parameters: dict[str, Any]
    draft_response: dict[str, Any]
    amount: Decimal
    currency: str
    expected_postcondition: str
    model_provider: str
    model_version: str
    prompt_version: str
    graph_version: str
    policy_version: str
    created_at: datetime
