from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Decision = Literal["approve_resolution", "block_and_review", "safe_retry", "reconcile"]


class EvaluationChecks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: bool
    retrieval: bool
    proposal: bool
    approval: bool
    execution: bool
    recovery: bool
    postcondition: bool | None


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^EVAL-\d{3}$")
    scenario: str
    category: Literal["happy_path", "safety", "failure_recovery"]
    expected_decision: Decision


class GoldenSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    cases: list[GoldenCase] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_cases(self) -> "GoldenSuite":
        ids = [case.id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("Golden workflow case IDs must be unique.")
        return self


class ObservedCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^EVAL-\d{3}$")
    actual_decision: Decision
    checks: EvaluationChecks
    evidence: str
    action: str
    approval: str
    failure_reason: str | None = None
    impact: str | None = None
    safety_disposition: str | None = None
    next_action: str | None = None


class ObservedSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["workflow-output-v2"]
    provenance: Literal["designed_fixture_not_runtime_observation"]
    results: list[ObservedCase] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_results(self) -> "ObservedSuite":
        ids = [result.case_id for result in self.results]
        if len(set(ids)) != len(ids):
            raise ValueError("Observed workflow fixture case IDs must be unique.")
        return self


class EvaluatedCase(BaseModel):
    id: str
    scenario: str
    category: str
    expected_decision: Decision
    observed: ObservedCase
    result: Literal["passed", "failed"]
    failed_checks: list[str]


class WorkflowEvaluation(BaseModel):
    golden_version: str
    observed_version: str
    evaluator: Literal["support-workflow-evaluator-v1"]
    evidence_tier: Literal["designed_fixture_not_runtime_observation"]
    cases: list[EvaluatedCase]
    total: int
    passed: int
    failed: int


def evaluate_workflow(golden_path: Path, observed_path: Path) -> WorkflowEvaluation:
    golden = GoldenSuite.model_validate_json(golden_path.read_text(encoding="utf-8"))
    observed_suite = ObservedSuite.model_validate_json(observed_path.read_text(encoding="utf-8"))
    golden_ids = {case.id for case in golden.cases}
    observed_ids = {case.case_id for case in observed_suite.results}
    if golden_ids != observed_ids:
        missing = sorted(golden_ids - observed_ids)
        extra = sorted(observed_ids - golden_ids)
        raise ValueError(f"Workflow fixture coverage mismatch; missing={missing}, extra={extra}.")
    observed_cases = {item.case_id: item for item in observed_suite.results}
    evaluated: list[EvaluatedCase] = []
    for expected in golden.cases:
        observed = observed_cases[expected.id]
        failed_checks = [
            name for name, value in observed.checks.model_dump().items() if value is False
        ]
        if observed.actual_decision != expected.expected_decision:
            failed_checks.insert(0, "decision_match")
        evaluated.append(
            EvaluatedCase(
                id=expected.id,
                scenario=expected.scenario,
                category=expected.category,
                expected_decision=expected.expected_decision,
                observed=observed,
                result="failed" if failed_checks else "passed",
                failed_checks=failed_checks,
            )
        )
    passed = sum(item.result == "passed" for item in evaluated)
    return WorkflowEvaluation(
        golden_version=golden.version,
        observed_version=observed_suite.version,
        evaluator="support-workflow-evaluator-v1",
        evidence_tier=observed_suite.provenance,
        cases=evaluated,
        total=len(evaluated),
        passed=passed,
        failed=len(evaluated) - passed,
    )
