from pathlib import Path

import pytest

from app.evaluation.workflow import evaluate_workflow

ROOT = Path(__file__).resolve().parents[2] / "evaluations" / "workflow"


def test_workflow_evaluation_keeps_known_failure_visible() -> None:
    result = evaluate_workflow(ROOT / "golden.json", ROOT / "observed.json")
    assert (result.total, result.passed, result.failed) == (8, 7, 1)
    assert result.evidence_tier == "designed_fixture_not_runtime_observation"
    failed = next(item for item in result.cases if item.result == "failed")
    assert failed.id == "EVAL-008"
    assert failed.failed_checks == ["postcondition"]
    assert failed.observed.safety_disposition is not None
    assert failed.observed.safety_disposition.startswith("No retry")


def test_workflow_evaluation_fails_closed_on_missing_observation(tmp_path: Path) -> None:
    observed = (
        (ROOT / "observed.json").read_text().replace('"case_id":"EVAL-008"', '"case_id":"EVAL-999"')
    )
    path = tmp_path / "observed.json"
    path.write_text(observed)
    with pytest.raises(ValueError, match="coverage mismatch"):
        evaluate_workflow(ROOT / "golden.json", path)
