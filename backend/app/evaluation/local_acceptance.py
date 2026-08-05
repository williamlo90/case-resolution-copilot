import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.evaluation.public_benchmark.storage import ensure_within

AcceptanceArea = Literal[
    "role_authority",
    "authentication_failure",
    "model_provider_failure",
    "case_intake_security",
    "action_recovery",
    "route_authority",
    "operational_readiness",
    "decision_generation",
    "policy_retrieval",
    "case_pagination",
    "legacy_boundary",
    "case_workspace",
    "workflow_evidence",
]
_REQUIRED_AREAS: frozenset[AcceptanceArea] = frozenset(
    {
        "role_authority",
        "authentication_failure",
        "model_provider_failure",
        "case_intake_security",
        "action_recovery",
        "route_authority",
        "operational_readiness",
        "decision_generation",
        "policy_retrieval",
        "case_pagination",
        "legacy_boundary",
        "case_workspace",
        "workflow_evidence",
    }
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocalAcceptanceCheck(StrictModel):
    id: str = Field(pattern=r"^[A-Z]+-\d{3}$")
    area: AcceptanceArea
    behavior: str = Field(min_length=10, max_length=500)
    test_file: str = Field(pattern=r"^tests/(?:unit|contract)/test_[a-z0-9_]+\.py$")
    test_selector: str = Field(pattern=r"^test_[a-z0-9_]+$")
    resource_class: Literal["unit", "contract"]
    external_dependency: Literal[False]

    @property
    def node_id(self) -> str:
        return f"{self.test_file}::{self.test_selector}"


class LocalAcceptanceMatrix(StrictModel):
    schema_version: Literal["local-release-acceptance-v1"]
    checks: list[LocalAcceptanceCheck] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_complete_matrix(self) -> "LocalAcceptanceMatrix":
        ids = [check.id for check in self.checks]
        node_ids = [check.node_id for check in self.checks]
        if len(set(ids)) != len(ids):
            raise ValueError("Local acceptance check IDs must be unique.")
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("Local acceptance test selectors must be unique.")
        areas = {check.area for check in self.checks}
        missing = sorted(_REQUIRED_AREAS - areas)
        if missing:
            raise ValueError(f"Local acceptance matrix is missing areas: {missing}")
        return self


class LocalAcceptanceValidation(StrictModel):
    validated_at: datetime
    checks: int = Field(ge=1)
    areas: dict[str, int]
    node_ids: list[str] = Field(min_length=1)
    resource_profile: Literal["single-process-unit-and-contract"] = (
        "single-process-unit-and-contract"
    )
    external_dependencies: Literal[0] = 0


def validate_local_acceptance_matrix(
    matrix_path: Path,
    *,
    backend_root: Path,
    validated_at: datetime,
) -> LocalAcceptanceValidation:
    root = backend_root.resolve()
    safe_matrix_path = ensure_within(root, matrix_path)
    matrix = LocalAcceptanceMatrix.model_validate_json(safe_matrix_path.read_text(encoding="utf-8"))
    for check in matrix.checks:
        test_path = ensure_within(root, root / check.test_file)
        if not test_path.is_file():
            raise ValueError(f"Acceptance test file is missing: {check.test_file}")
        source = test_path.read_text(encoding="utf-8")
        pattern = rf"^def\s+{re.escape(check.test_selector)}\s*\("
        if re.search(pattern, source, flags=re.MULTILINE) is None:
            raise ValueError(f"Acceptance test selector is missing: {check.node_id}")
    return LocalAcceptanceValidation(
        validated_at=validated_at,
        checks=len(matrix.checks),
        areas=dict(Counter(check.area for check in matrix.checks)),
        node_ids=[check.node_id for check in matrix.checks],
    )
