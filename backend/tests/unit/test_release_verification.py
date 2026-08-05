import sys
from pathlib import Path

import pytest

import scripts.run_release_verification as release_verification
from scripts.run_release_verification import (
    Check,
    CheckResult,
    parse_counts,
    redact_sensitive_text,
    run_checks,
    validate_evidence_path,
)


def test_release_checks_preserve_the_active_virtual_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    virtual_python = ".venv/bin/python"
    monkeypatch.setattr(sys, "executable", virtual_python)
    monkeypatch.setattr(
        release_verification,
        "_required_executable",
        lambda _name: "git",
    )
    monkeypatch.setattr(
        release_verification,
        "_frontend_binary",
        lambda name: name,
    )

    checks = release_verification.default_checks()

    assert checks[1].command[0] == virtual_python


def _result(name: str, output: str, *, passed: bool = True) -> CheckResult:
    return {
        "name": name,
        "passed": passed,
        "return_code": 0 if passed else 1,
        "duration_seconds": 0.01,
        "timeout_seconds": 30,
        "output": output,
        "output_tail": output,
    }


def test_release_counts_are_derived_from_tool_output() -> None:
    counts = parse_counts(
        [
            _result("backend_types", "Success: no issues found in 301 source files"),
            _result("backend_tests", "324 passed in 9.1s"),
            _result(
                "local_acceptance",
                "65 passed in 1.2s\nstatus=passed phase=execute checks=50 areas=13",
            ),
            _result(
                "workflow_traceability",
                "21 passed in 0.8s\nstatus=passed phase=execute scenarios=8 proofs=19",
            ),
            _result(
                "frontend_tests",
                "Test Files 42 passed (42)\nTests 125 passed (125)",
            ),
        ]
    )

    assert counts == {
        "checks_passed": 5,
        "backend_source_files_typed": 301,
        "backend_tests": 324,
        "acceptance_controls": 50,
        "acceptance_areas": 13,
        "acceptance_test_variants": 65,
        "workflow_scenarios": 8,
        "workflow_proofs": 19,
        "workflow_test_variants": 21,
        "frontend_test_files": 42,
        "frontend_tests": 125,
    }


def test_release_gate_stops_after_the_first_failure(tmp_path: Path) -> None:
    checks = (
        Check("first", ("first",), tmp_path, 30),
        Check("second", ("second",), tmp_path, 30),
        Check("third", ("third",), tmp_path, 30),
    )
    calls: list[str] = []

    def execute(check: Check) -> CheckResult:
        calls.append(check.name)
        return _result(
            check.name,
            "failed" if check.name == "second" else "passed",
            passed=check.name != "second",
        )

    results, passed = run_checks(checks, executor=execute)

    assert passed is False
    assert calls == ["first", "second"]
    assert [result["name"] for result in results] == calls


def test_release_evidence_path_cannot_escape_project_evidence_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="must stay inside"):
        validate_evidence_path(tmp_path / "outside.json")


def test_release_output_redacts_common_secret_shapes() -> None:
    value = "postgresql+psycopg://user:pass@host/db api_key=super-secret sk_test_123456789"

    redacted = redact_sensitive_text(value)

    assert "user:pass" not in redacted
    assert "super-secret" not in redacted
    assert "sk_test_123456789" not in redacted
    assert redacted.count("[REDACTED") == 3


def test_github_quality_gate_is_review_only_and_resource_bounded() -> None:
    project_root = Path(__file__).resolve().parents[3]
    workflow = (project_root / ".github" / "workflows" / "quality-gate.yml").read_text(
        encoding="utf-8"
    )

    assert "  pull_request:" in workflow
    assert "      - main" in workflow
    assert '      - "backend/**"' in workflow
    assert '      - "frontend/**"' in workflow
    assert "  workflow_dispatch:" in workflow
    assert "  push:" not in workflow
    assert workflow.count("runs-on:") == 1
    assert "timeout-minutes: 20" in workflow
    assert "scripts.run_release_verification" in workflow
    assert "pip-audit==2.10.1" in workflow
    assert "pnpm audit --prod --audit-level high" in workflow
    assert "pnpm build" in workflow
    assert "playwright" not in workflow.lower()
    assert "docker" not in workflow.lower()
