"""Normalized evidence contract. Observations come from adapters, never from oracle labels."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.resolution import ActionReadback
from app.evaluation.case_resolution_v2.contracts import (
    ActionExpectation,
    ContractModel,
    Digest,
    Name,
    OracleLabel,
    PolicyExpectation,
    Terminal,
)

SCORER_VERSION = "case-resolution-v2-scorer-1"


class RunConfig(ContractModel):
    model_version: Name
    prompt_version: Name
    runtime_adapter_version: Name
    policy_snapshot_sha256: Digest
    environment: Name
    seed: int = Field(ge=0, strict=True)


class Evidence(ContractModel):
    id: Name
    facts: dict[str, str] = Field(min_length=1)
    source: Name


class Scenario(ContractModel):
    case_id: Name
    family_id: Name
    sop_family_id: Name
    domain: Literal["billing", "refund", "account_recovery"]
    tenant_id: Name
    request: Name
    as_of: datetime
    deadline: datetime
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    policies: tuple[dict[str, str], ...]
    environment: dict[str, str]
    tags: tuple[Name, ...]
    critical: bool


class GoldenLabel(ContractModel):
    """V2 adds explicit semantic assertions without changing Phase 0 measurement thresholds."""

    oracle: OracleLabel
    fact_values: dict[str, str]
    fact_sources: dict[str, tuple[Name, ...]]
    semantic_assertions: dict[str, str]
    disposition: Literal["resolve", "escalate", "request_information", "decline"]
    forbidden_claims: tuple[Name, ...]
    authorized_roles: tuple[Name, ...]
    adjudication: Literal["agent_reviewed_not_independent_human_review"]


class Fact(ContractModel):
    value: str
    evidence_ids: tuple[Name, ...]


class Approval(ContractModel):
    role: Name
    tenant_id: Name
    payload_sha256: Digest
    approved_at: datetime
    expires_at: datetime


class Operation(ContractModel):
    intent: ActionExpectation
    operation_id: Name
    external_reference: Name
    executed_at: datetime
    approval: Approval | None
    readback: ActionReadback | None


class Escalation(ContractModel):
    queue: Name
    tenant_id: Name
    routing_id: Name
    assigned_actor: Name
    acknowledged_actor: Name
    acknowledged_role: Name
    routed_at: datetime
    acknowledged_at: datetime


class Completion(ContractModel):
    event_id: Name
    tenant_id: Name
    occurred_at: datetime
    verified_operation_ids: tuple[Name, ...]
    communication_reference: Name
    attested_role: Name


class Observation(ContractModel):
    version: Literal["case-resolution-v2-observation-1"]
    case_id: Name
    input_sha256: Digest
    tenant_id: Name
    observed_at: datetime
    status: Literal["observed", "provider_failure", "invalid", "missing"]
    error_code: Name | None = None
    facts: dict[str, Fact]
    gaps: tuple[Name, ...]
    policies: tuple[PolicyExpectation, ...]
    policy_status: Literal["applicable", "missing", "conflicting"]
    semantic_assertions: dict[str, str]
    disposition: Literal["resolve", "escalate", "request_information", "decline"]
    proposed_actions: tuple[ActionExpectation, ...]
    operations: tuple[Operation, ...]
    claims: tuple[Name, ...]
    terminal: Terminal
    completion: Completion | None
    escalation: Escalation | None
    human_touches: int = Field(ge=0)


class Grade(ContractModel):
    case_id: Name
    family_id: Name
    domain: str
    status: str
    expected_terminal: Terminal
    observed_terminal: Terminal | None
    components: dict[str, bool]
    policy_correct: bool
    correct_completion: bool
    automated_resolution: bool
    verified_actions: int
    action_denominator: int
    failures: tuple[str, ...]
