import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.local_acceptance import validate_local_acceptance_matrix
from app.evaluation.public_benchmark.storage import atomic_write_json, sha256_file

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_MATRIX_PATH = BACKEND_ROOT / "evaluations" / "acceptance" / "local_release_matrix.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / ".codex-runtime" / "local-acceptance.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the single-process local unit/contract release acceptance matrix."
    )
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate matrix coverage and selectors without running pytest.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Hard timeout for the selected single-process unit test run.",
    )
    arguments = parser.parse_args()
    if arguments.timeout_seconds < 10 or arguments.timeout_seconds > 300:
        parser.error("--timeout-seconds must be between 10 and 300.")
    now = datetime.now(UTC)
    validation = validate_local_acceptance_matrix(
        arguments.matrix,
        backend_root=BACKEND_ROOT,
        validated_at=now,
    )
    if arguments.validate_only:
        print(
            f"status=passed phase=validate checks={validation.checks} "
            f"areas={len(validation.areas)} external_dependencies=0"
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
        "schema_version": "local-release-acceptance-report-v1",
        "executed_at": now.isoformat(),
        "matrix_sha256": sha256_file(arguments.matrix),
        "checks": validation.checks,
        "areas": validation.areas,
        "resource_profile": validation.resource_profile,
        "external_dependencies": validation.external_dependencies,
        "timeout_seconds": arguments.timeout_seconds,
        "pytest_exit_code": exit_code,
        "status": "passed" if exit_code == 0 else "failed",
    }
    atomic_write_json(PROJECT_ROOT, arguments.report, report)
    print(
        f"status={report['status']} phase=execute checks={validation.checks} "
        f"areas={len(validation.areas)} report={arguments.report}"
    )
    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
