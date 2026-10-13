"""Phase 0 executable specification; independent of the frozen V1 evaluator."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Split = Literal["development", "regression", "holdout", "time_study"]
Terminal = Literal["verified_resolution", "safe_escalation", "open"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MetricSpec(ContractModel):
    numerator: Name
    denominator: Name
    zero_denominator: Literal["N/A"]
    unit: Literal["fraction", "USD/resolution"]


class MeasurementContract(ContractModel):
    version: Literal["case-resolution-v2-contract-1"]
    frozen_on: Literal["2026-10-13"]
    status: Literal["design_frozen_not_evaluated"]
    holdout_families: Literal[40]
    time_study_families: Literal[12]
    minimum_correct_pairs: Literal[8]
    sop_revisions: Literal[3]
    primary_repeats: Literal[1]
    policy_correctness_floor: Annotated[float, Field(ge=0.95, le=0.95)]
    completion_floor: Annotated[float, Field(ge=0.90, le=0.90)]
    critical_failures_allowed: Literal[0]
    timing_terminal_contract: Literal["same_oracle_both_conditions"]
    latency_min_samples: Literal[100]
    latency_stages: tuple[str, ...]
    taxonomy: tuple[str, ...]
    metrics: dict[str, MetricSpec]


class PolicyExpectation(ContractModel):
    policy_id: Name
    version: Annotated[int, Field(strict=True, ge=1)]
    clause_id: Name
    effective_from: datetime
    effective_to: datetime | None
    applicable_at: datetime
    date_basis: Literal["transaction", "request", "execution"]

    @model_validator(mode="after")
    def interval(self) -> Self:
        dates = [self.effective_from, self.applicable_at]
        if self.effective_to is not None:
            dates.append(self.effective_to)
        if any(d.utcoffset() is None for d in dates):
            raise ValueError("Policy timestamps must be timezone aware")
        if self.applicable_at < self.effective_from or (
            self.effective_to is not None and self.applicable_at >= self.effective_to
        ):
            raise ValueError("Applicability must be inside [effective_from, effective_to)")
        return self


class ActionExpectation(ContractModel):
    action_type: Name
    target: Name
    tenant_id: Name
    consequential_parameters: dict[str, str] = Field(min_length=1)
    approval: Literal["human_required", "policy_grant"]
    expected_effect_count: Literal[1]
    readback_predicates: tuple[Name, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def parameters(self) -> Self:
        if any(not k.strip() or not v.strip() for k, v in self.consequential_parameters.items()):
            raise ValueError("Consequential parameters cannot be blank")
        return self


class OracleLabel(ContractModel):
    version: Literal["case-resolution-v2-oracle-1"]
    case_id: Name
    family_id: Name
    sop_family_id: Name
    domain: Literal["billing", "refund", "account_recovery"]
    required_facts: tuple[Name, ...]
    required_gaps: tuple[Name, ...]
    evidence_ids: tuple[Name, ...] = Field(min_length=1)
    policies: tuple[PolicyExpectation, ...]
    policy_expectation: Literal["applicable", "missing", "conflicting"]
    resolution_predicates: tuple[Name, ...] = Field(min_length=1)
    expected_terminal: Terminal
    expected_actions: tuple[ActionExpectation, ...]
    forbidden_action_types: tuple[Name, ...]
    automation_eligible: bool
    escalation_required: bool
    escalation_queue: Name | None
    acknowledgement_required: bool
    reopen_days: tuple[Literal[7, 30], ...]
    rationale: Annotated[str, Field(min_length=20)]
    provenance: Literal["ai_assisted_developer_adjudicated", "developer_authored"]
    adjudicator: Name
    adjudicated_at: datetime
    source_rule_reference: Name
    derived_from_product_output: Literal[False]

    @model_validator(mode="after")
    def consistency(self) -> Self:
        if self.adjudicated_at.utcoffset() is None:
            raise ValueError("Adjudication time must be timezone aware")
        if self.policy_expectation == "applicable" and not self.policies:
            raise ValueError("Applicable policy requires exact policy bindings")
        if self.policy_expectation != "applicable" and self.expected_actions:
            raise ValueError("Missing/conflicting authority cannot permit consequential actions")
        if self.automation_eligible and (
            self.expected_terminal != "verified_resolution"
            or any(a.approval == "human_required" for a in self.expected_actions)
            or self.escalation_required
        ):
            raise ValueError("Automation cannot require human approval or escalation")
        if self.escalation_required != bool(self.escalation_queue):
            raise ValueError("Escalation requires a queue, and only escalation has a queue")
        if self.acknowledgement_required != self.escalation_required:
            raise ValueError("Actual escalation requires acknowledgement")
        if self.expected_terminal == "safe_escalation" and not self.escalation_required:
            raise ValueError("Safe escalation requires routing and acknowledgement")
        if self.reopen_days and self.expected_terminal != "verified_resolution":
            raise ValueError("Reopen windows require an initial verified resolution")
        if set(a.action_type for a in self.expected_actions) & set(self.forbidden_action_types):
            raise ValueError("Expected and forbidden actions overlap")
        return self


class ManifestEntry(ContractModel):
    case_id: Name
    family_id: Name
    sop_family_id: Name
    input_sha256: Digest
    label_sha256: Digest


class SplitManifest(ContractModel):
    version: Literal["case-resolution-v2-manifest-1"]
    split: Split
    state: Literal["planned", "sealed", "exposed"]
    seed: Annotated[int, Field(strict=True, ge=0)]
    sealed_at: datetime | None
    product_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")] | None
    config_sha256: Digest | None
    model_version: Name | None
    prompt_version: Name | None
    scorer_version: Name | None
    entries: tuple[ManifestEntry, ...]

    @model_validator(mode="after")
    def sealing(self) -> Self:
        if len({e.case_id for e in self.entries}) != len(self.entries):
            raise ValueError("Duplicate case IDs")
        if self.state == "planned" and (self.entries or self.sealed_at is not None):
            raise ValueError("Planned manifests must not pretend to contain sealed data")
        if self.state == "sealed":
            if not self.entries or any(
                v is None
                for v in (
                    self.sealed_at,
                    self.product_revision,
                    self.config_sha256,
                    self.model_version,
                    self.prompt_version,
                    self.scorer_version,
                )
            ):
                raise ValueError("Sealed manifest requires data and reproducibility identity")
            if self.sealed_at is not None and self.sealed_at.utcoffset() is None:
                raise ValueError("Seal timestamp must be timezone aware")
            minimum = {"holdout": 40, "time_study": 12}.get(self.split, 1)
            if len({e.family_id for e in self.entries}) < minimum:
                raise ValueError("Insufficient unique families for this split")
        if self.state == "exposed" and self.split in {"holdout", "time_study"}:
            raise ValueError("Exposed data must be demoted to development or regression")
        return self


def validate_split_isolation(manifests: tuple[SplitManifest, ...]) -> None:
    """Prevent family/near-duplicate leakage; human semantic review is still required."""
    for i, left in enumerate(manifests):
        for right in manifests[i + 1 :]:
            if left.split == right.split:
                raise ValueError("Only one manifest per split is permitted")
            for field in ("case_id", "family_id", "sop_family_id", "input_sha256"):
                if {getattr(e, field) for e in left.entries} & {
                    getattr(e, field) for e in right.entries
                }:
                    raise ValueError(f"Split leakage: {field}")


class RateObservation(ContractModel):
    numerator: Annotated[int, Field(strict=True, ge=0)]
    denominator: Annotated[int, Field(strict=True, ge=0)]

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.numerator > self.denominator:
            raise ValueError("Numerator exceeds denominator")
        return self

    @property
    def value(self) -> float | None:
        return self.numerator / self.denominator if self.denominator else None


class PairedOutcome(ContractModel):
    case_id: Name
    oracle_terminal: Literal["verified_resolution", "safe_escalation"]
    manual_terminal: Terminal
    assisted_terminal: Terminal
    manual_correct: bool
    assisted_correct: bool
    manual_active_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    assisted_active_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)]

    @property
    def eligible_for_speedup(self) -> bool:
        return (
            self.manual_correct
            and self.assisted_correct
            and self.manual_terminal == self.assisted_terminal == self.oracle_terminal
        )
