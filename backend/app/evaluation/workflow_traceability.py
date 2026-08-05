import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evaluation.public_benchmark.storage import ensure_within

WorkflowStage = Literal[
    "decision",
    "policy",
    "review",
    "authority",
    "action",
    "recovery",
]
_REQUIRED_SCENARIOS = {f"EVAL-{index:03d}" for index in range(1, 9)}
_REQUIRED_STAGES: frozenset[WorkflowStage] = frozenset(
    {"decision", "policy", "review", "authority", "action", "recovery"}
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkflowProof(StrictModel):
    test_file: str = Field(pattern=r"^tests/(?:unit|contract)/test_[a-z0-9_]+\.py$")
    test_selector: str = Field(pattern=r"^test_[a-z0-9_]+$")
    supports: list[WorkflowStage] = Field(min_length=1)

    @property
    def node_id(self) -> str:
        return f"{self.test_file}::{self.test_selector}"


class WorkflowScenarioTrace(StrictModel):
    case_id: str = Field(pattern=r"^EVAL-\d{3}$")
    claim: str = Field(min_length=20, max_length=500)
    proofs: list[WorkflowProof] = Field(min_length=2)


class WorkflowTraceabilityMatrix(StrictModel):
    schema_version: Literal["workflow-traceability-v1"]
    evidence_scope: Literal["composed-production-test-trace"]
    scenarios: list[WorkflowScenarioTrace] = Field(min_length=1)

    @model_validator(mode="after")
    def require_complete_unique_trace(self) -> "WorkflowTraceabilityMatrix":
        scenario_ids = [scenario.case_id for scenario in self.scenarios]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("Workflow trace scenario IDs must be unique.")
        if set(scenario_ids) != _REQUIRED_SCENARIOS:
            missing = sorted(_REQUIRED_SCENARIOS - set(scenario_ids))
            extra = sorted(set(scenario_ids) - _REQUIRED_SCENARIOS)
            raise ValueError(
                f"Workflow trace scenario coverage mismatch; missing={missing}, extra={extra}."
            )
        node_ids = [proof.node_id for scenario in self.scenarios for proof in scenario.proofs]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("Workflow trace test selectors must be unique.")
        stages = {
            stage
            for scenario in self.scenarios
            for proof in scenario.proofs
            for stage in proof.supports
        }
        missing_stages = sorted(_REQUIRED_STAGES - stages)
        if missing_stages:
            raise ValueError(f"Workflow trace is missing production stages: {missing_stages}.")
        return self


class WorkflowTraceabilityValidation(StrictModel):
    validated_at: datetime
    scenarios: int = Field(ge=1)
    proofs: int = Field(ge=1)
    stages: dict[str, int]
    node_ids: list[str] = Field(min_length=1)
    evidence_scope: Literal["composed-production-test-trace"]
    resource_profile: Literal["single-process-unit-and-contract"] = (
        "single-process-unit-and-contract"
    )
    external_dependencies: Literal[0] = 0


def validate_workflow_traceability(
    matrix_path: Path,
    *,
    backend_root: Path,
    validated_at: datetime,
) -> WorkflowTraceabilityValidation:
    root = backend_root.resolve()
    safe_matrix_path = ensure_within(root, matrix_path)
    matrix = WorkflowTraceabilityMatrix.model_validate_json(
        safe_matrix_path.read_text(encoding="utf-8")
    )
    node_ids: list[str] = []
    stages: Counter[str] = Counter()
    for scenario in matrix.scenarios:
        for proof in scenario.proofs:
            test_path = ensure_within(root, root / proof.test_file)
            if not test_path.is_file():
                raise ValueError(f"Workflow trace test file is missing: {proof.test_file}")
            source = test_path.read_text(encoding="utf-8")
            pattern = rf"^def\s+{re.escape(proof.test_selector)}\s*\("
            if re.search(pattern, source, flags=re.MULTILINE) is None:
                raise ValueError(f"Workflow trace test selector is missing: {proof.node_id}")
            node_ids.append(proof.node_id)
            stages.update(proof.supports)
    return WorkflowTraceabilityValidation(
        validated_at=validated_at,
        scenarios=len(matrix.scenarios),
        proofs=len(node_ids),
        stages=dict(stages),
        node_ids=node_ids,
        evidence_scope=matrix.evidence_scope,
    )
