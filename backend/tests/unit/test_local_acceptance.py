import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.evaluation.local_acceptance import validate_local_acceptance_matrix

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = BACKEND_ROOT / "evaluations" / "acceptance" / "local_release_matrix.json"
NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def test_local_acceptance_matrix_covers_required_failure_and_authority_areas() -> None:
    result = validate_local_acceptance_matrix(
        MATRIX_PATH,
        backend_root=BACKEND_ROOT,
        validated_at=NOW,
    )

    assert result.checks == 54
    assert result.areas == {
        "role_authority": 6,
        "authentication_failure": 3,
        "model_provider_failure": 2,
        "case_intake_security": 3,
        "action_recovery": 6,
        "route_authority": 7,
        "operational_readiness": 6,
        "decision_generation": 5,
        "policy_retrieval": 5,
        "case_pagination": 6,
        "legacy_boundary": 1,
        "case_workspace": 3,
        "workflow_evidence": 1,
    }
    assert result.resource_profile == "single-process-unit-and-contract"
    assert result.external_dependencies == 0


def test_local_acceptance_matrix_rejects_missing_test_selector(tmp_path: Path) -> None:
    test_root = tmp_path / "backend"
    test_file = test_root / "tests/unit/test_example.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_existing() -> None:\n    assert True\n", encoding="utf-8")
    checks = [
        {
            "id": f"{prefix}-001",
            "area": area,
            "behavior": "This acceptance behavior is intentionally explicit.",
            "test_file": "tests/unit/test_example.py",
            "test_selector": "test_missing" if index == 0 else "test_existing",
            "resource_class": "unit",
            "external_dependency": False,
        }
        for index, (prefix, area) in enumerate(
            (
                ("ROLE", "role_authority"),
                ("AUTH", "authentication_failure"),
                ("MODEL", "model_provider_failure"),
                ("INTAKE", "case_intake_security"),
                ("ACTION", "action_recovery"),
                ("ROUTE", "route_authority"),
                ("READY", "operational_readiness"),
                ("DECISION", "decision_generation"),
                ("RETRIEVAL", "policy_retrieval"),
                ("PAGE", "case_pagination"),
                ("LEGACY", "legacy_boundary"),
                ("WORKSPACE", "case_workspace"),
                ("TRACE", "workflow_evidence"),
            )
        )
    ]
    for index, check in enumerate(checks[1:], start=1):
        selector = f"test_existing_{index}"
        check["test_selector"] = selector
        with test_file.open("a", encoding="utf-8") as handle:
            handle.write(f"\ndef {selector}() -> None:\n    assert True\n")
    matrix_path = test_root / "evaluations/acceptance/matrix.json"
    matrix_path.parent.mkdir(parents=True)
    matrix_path.write_text(
        json.dumps(
            {
                "schema_version": "local-release-acceptance-v1",
                "checks": checks,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Acceptance test selector is missing"):
        validate_local_acceptance_matrix(
            matrix_path,
            backend_root=test_root,
            validated_at=NOW,
        )
