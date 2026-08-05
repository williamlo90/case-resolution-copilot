import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.evaluation.workflow_traceability import validate_workflow_traceability

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = BACKEND_ROOT / "evaluations" / "workflow" / "traceability.json"
NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def test_workflow_traceability_covers_all_scenarios_and_production_stages() -> None:
    result = validate_workflow_traceability(
        MATRIX_PATH,
        backend_root=BACKEND_ROOT,
        validated_at=NOW,
    )

    assert result.scenarios == 8
    assert result.proofs == 19
    assert set(result.stages) == {
        "decision",
        "policy",
        "review",
        "authority",
        "action",
        "recovery",
    }
    assert result.evidence_scope == "composed-production-test-trace"
    assert result.resource_profile == "single-process-unit-and-contract"
    assert result.external_dependencies == 0


def test_workflow_traceability_rejects_a_missing_test_selector(
    tmp_path: Path,
) -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    matrix["scenarios"][0]["proofs"][0]["test_selector"] = "test_missing"
    sources: dict[str, list[str]] = {}
    for scenario in matrix["scenarios"]:
        for proof in scenario["proofs"]:
            if proof["test_selector"] == "test_missing":
                continue
            sources.setdefault(proof["test_file"], []).append(
                f"def {proof['test_selector']}() -> None:\n    assert True\n"
            )
    for relative_path, definitions in sources.items():
        test_path = tmp_path / relative_path
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text("\n".join(definitions), encoding="utf-8")
    matrix_path = tmp_path / "evaluations" / "workflow" / "traceability.json"
    matrix_path.parent.mkdir(parents=True)
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    with pytest.raises(ValueError, match="test selector is missing"):
        validate_workflow_traceability(
            matrix_path,
            backend_root=tmp_path,
            validated_at=NOW,
        )
