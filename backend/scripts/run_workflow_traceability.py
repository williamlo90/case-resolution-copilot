import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.public_benchmark.storage import atomic_write_json, sha256_file
from app.evaluation.workflow_traceability import validate_workflow_traceability

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_MATRIX_PATH = BACKEND_ROOT / "evaluations" / "workflow" / "traceability.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / ".codex-runtime" / "workflow-traceability.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate or execute the bounded production-test trace for workflow scenarios."
        )
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate scenario coverage and test selectors without running pytest.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="Hard timeout for the selected single-process unit and contract tests.",
    )
    arguments = parser.parse_args()
    if arguments.timeout_seconds < 10 or arguments.timeout_seconds > 300:
        parser.error("--timeout-seconds must be between 10 and 300.")

    now = datetime.now(UTC)
    validation = validate_workflow_traceability(
        arguments.matrix,
        backend_root=BACKEND_ROOT,
        validated_at=now,
    )
    if arguments.validate_only:
        print(
            f"status=passed phase=validate scenarios={validation.scenarios} "
            f"proofs={validation.proofs} external_dependencies=0"
        )
        return

    command = [sys.executable, "-m", "pytest", "-q", *validation.node_ids]
    try:
        completed = subprocess.run(
            command,
            cwd=BACKEND_ROOT,
            check=False,
            timeout=arguments.timeout_seconds,
        )
        exit_code = completed.returncode
    except subprocess.TimeoutExpired:
        exit_code = 124
    report = {
        "schema_version": "workflow-traceability-report-v1",
        "executed_at": now.isoformat(),
        "matrix_sha256": sha256_file(arguments.matrix),
        "scenarios": validation.scenarios,
        "proofs": validation.proofs,
        "stages": validation.stages,
        "evidence_scope": validation.evidence_scope,
        "resource_profile": validation.resource_profile,
        "external_dependencies": validation.external_dependencies,
        "timeout_seconds": arguments.timeout_seconds,
        "pytest_exit_code": exit_code,
        "status": "passed" if exit_code == 0 else "failed",
    }
    atomic_write_json(PROJECT_ROOT, arguments.report, report)
    print(
        f"status={report['status']} phase=execute scenarios={validation.scenarios} "
        f"proofs={validation.proofs} report={arguments.report}"
    )
    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
