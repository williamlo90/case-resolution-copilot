from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
EVIDENCE_ROOT = PROJECT_ROOT / "docs" / "evidence" / "release-verification"
DEFAULT_EVIDENCE_PATH = EVIDENCE_ROOT / f"{datetime.now(UTC).date().isoformat()}.json"


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    cwd: Path
    timeout_seconds: int


class CheckResult(TypedDict):
    name: str
    passed: bool
    return_code: int
    duration_seconds: float
    timeout_seconds: int
    output: str
    output_tail: str


CheckExecutor = Callable[[Check], CheckResult]


def main() -> int:
    arguments = _arguments()
    try:
        checks = default_checks()
        if arguments.list_checks:
            for check in checks:
                relative_cwd = check.cwd.relative_to(PROJECT_ROOT)
                print(
                    f"{check.name}: cwd={relative_cwd or Path('.')} "
                    f"timeout={check.timeout_seconds}s"
                )
            return 0

        evidence_path: Path | None = None
        if arguments.write_evidence is not None:
            evidence_path = validate_evidence_path(arguments.write_evidence)
            if _git("status", "--porcelain"):
                print(
                    "ERROR: committed release evidence requires a clean worktree.",
                    file=sys.stderr,
                )
                return 2

        results, passed = run_checks(checks)
        if not passed:
            print("Release verification failed; no evidence was written.", file=sys.stderr)
            return 1

        evidence = build_evidence(results)
        if evidence_path is not None:
            atomic_write_json(evidence_path, evidence)
            print(f"Evidence written to {evidence_path.relative_to(PROJECT_ROOT)}")
        else:
            print(json.dumps(evidence["counts"], indent=2))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {redact_sensitive_text(str(error))}", file=sys.stderr)
        return 2


def default_checks() -> tuple[Check, ...]:
    git = _required_executable("git")
    python = sys.executable
    tsc = _frontend_binary("tsc")
    eslint = _frontend_binary("eslint")
    vitest = _frontend_binary("vitest")
    return (
        Check("repository_diff", (git, "diff", "--check"), PROJECT_ROOT, 30),
        Check(
            "backend_lint",
            (python, "-m", "ruff", "check", "app", "tests", "scripts"),
            BACKEND_ROOT,
            120,
        ),
        Check(
            "backend_types",
            (python, "-m", "mypy", "app", "tests", "scripts"),
            BACKEND_ROOT,
            180,
        ),
        Check(
            "repository_secret_scan",
            (python, "-m", "scripts.check_repository_secrets"),
            BACKEND_ROOT,
            60,
        ),
        Check(
            "migration_graph",
            (python, "-m", "scripts.check_migration_graph"),
            BACKEND_ROOT,
            60,
        ),
        Check(
            "case_transport_contract",
            (python, "-m", "scripts.check_case_transport_contract"),
            BACKEND_ROOT,
            60,
        ),
        Check(
            "backend_tests",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "tests/unit",
                "tests/contract",
                "tests/integration/provider_simulator/test_simulator.py",
            ),
            BACKEND_ROOT,
            180,
        ),
        Check(
            "local_acceptance",
            (
                python,
                "-m",
                "scripts.run_local_acceptance",
                "--timeout-seconds",
                "90",
            ),
            BACKEND_ROOT,
            120,
        ),
        Check(
            "workflow_traceability",
            (
                python,
                "-m",
                "scripts.run_workflow_traceability",
                "--timeout-seconds",
                "90",
            ),
            BACKEND_ROOT,
            120,
        ),
        Check("frontend_types", (tsc, "--noEmit"), FRONTEND_ROOT, 120),
        Check("frontend_lint", (eslint, "."), FRONTEND_ROOT, 120),
        Check(
            "frontend_tests",
            (vitest, "run", "--maxWorkers=1", "--no-file-parallelism"),
            FRONTEND_ROOT,
            180,
        ),
    )


def run_checks(
    checks: Sequence[Check],
    *,
    executor: CheckExecutor | None = None,
) -> tuple[list[CheckResult], bool]:
    execute = executor or run_check
    results: list[CheckResult] = []
    for check in checks:
        result = execute(check)
        results.append(result)
        state = "PASS" if result["passed"] else "FAIL"
        print(f"[{state}] {check.name} ({result['duration_seconds']:.2f}s)")
        if not result["passed"]:
            if result["output_tail"]:
                print(result["output_tail"], file=sys.stderr)
            return results, False
    return results, True


def run_check(check: Check) -> CheckResult:
    started = time.perf_counter()
    environment = os.environ.copy()
    environment.update(
        {
            "CI": "true",
            "FORCE_COLOR": "0",
            "NO_COLOR": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    try:
        completed = subprocess.run(
            list(check.command),
            cwd=check.cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=check.timeout_seconds,
        )
        return_code = completed.returncode
        output = f"{completed.stdout}\n{completed.stderr}".strip()
    except subprocess.TimeoutExpired as error:
        return_code = 124
        output = (
            f"{_timeout_output(error.stdout)}\n{_timeout_output(error.stderr)}\n"
            f"Timed out after {check.timeout_seconds} seconds."
        ).strip()

    redacted_output = redact_sensitive_text(output)
    return {
        "name": check.name,
        "passed": return_code == 0,
        "return_code": return_code,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "timeout_seconds": check.timeout_seconds,
        "output": redacted_output,
        "output_tail": "\n".join(redacted_output.splitlines()[-40:]),
    }


def build_evidence(results: Sequence[CheckResult]) -> dict[str, object]:
    return {
        "schema_version": "case-resolution-copilot-release-verification-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "source": {
            "git_commit": _git("rev-parse", "HEAD"),
            "branch": _git("branch", "--show-current"),
            "worktree_clean_at_start": True,
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "node": _version(_required_executable("node")),
        },
        "resource_profile": {
            "execution": "serial_fail_fast",
            "frontend_workers": 1,
            "browser_processes": 0,
            "application_servers": 0,
            "containers": 0,
            "external_dependencies": 0,
        },
        "counts": parse_counts(results),
        "checks": [
            {
                "name": result["name"],
                "passed": result["passed"],
                "duration_seconds": result["duration_seconds"],
                "timeout_seconds": result["timeout_seconds"],
            }
            for result in results
        ],
        "excluded_gates": [
            "database integration against Neon",
            "real-provider Decision Brief evaluation",
            "local production build",
            "local browser automation",
            "dependency audit requiring network access",
            "load, stress, and concurrency testing",
        ],
        "claim_boundary": [
            (
                "This report proves a clean, serial local source and contract gate "
                "for the recorded commit."
            ),
            (
                "It is not an independent security assessment or a production-scale "
                "reliability result."
            ),
            (
                "Database, provider, hosted-browser, and user-research evidence "
                "are recorded separately."
            ),
            "Public records and synthetic controls are not complete real-client business cases.",
        ],
    }


def parse_counts(results: Sequence[CheckResult]) -> dict[str, int]:
    output_by_name = {result["name"]: result["output"] for result in results}
    counts: dict[str, int] = {
        "checks_passed": sum(1 for result in results if result["passed"]),
    }
    _add_match(
        counts,
        "backend_source_files_typed",
        r"Success: no issues found in (\d+) source files",
        output_by_name.get("backend_types", ""),
    )
    _add_match(
        counts,
        "backend_tests",
        r"(\d+) passed(?:,| in)",
        output_by_name.get("backend_tests", ""),
    )
    _add_match(
        counts,
        "acceptance_controls",
        r"checks=(\d+)",
        output_by_name.get("local_acceptance", ""),
    )
    _add_match(
        counts,
        "acceptance_areas",
        r"areas=(\d+)",
        output_by_name.get("local_acceptance", ""),
    )
    _add_match(
        counts,
        "acceptance_test_variants",
        r"(\d+) passed(?:,| in)",
        output_by_name.get("local_acceptance", ""),
    )
    _add_match(
        counts,
        "workflow_scenarios",
        r"scenarios=(\d+)",
        output_by_name.get("workflow_traceability", ""),
    )
    _add_match(
        counts,
        "workflow_proofs",
        r"proofs=(\d+)",
        output_by_name.get("workflow_traceability", ""),
    )
    _add_match(
        counts,
        "workflow_test_variants",
        r"(\d+) passed(?:,| in)",
        output_by_name.get("workflow_traceability", ""),
    )
    _add_match(
        counts,
        "frontend_test_files",
        r"Test Files\s+(\d+) passed",
        output_by_name.get("frontend_tests", ""),
    )
    _add_match(
        counts,
        "frontend_tests",
        r"Tests\s+(\d+) passed",
        output_by_name.get("frontend_tests", ""),
    )
    return counts


def validate_evidence_path(candidate: Path) -> Path:
    candidate_path = candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
    resolved = candidate_path.resolve()
    evidence_root = EVIDENCE_ROOT.resolve()
    if resolved == evidence_root or not resolved.is_relative_to(evidence_root):
        raise ValueError("evidence path must stay inside docs/evidence/release-verification")
    if resolved.suffix.lower() != ".json":
        raise ValueError("evidence path must use the .json extension")
    return resolved


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(payload, temporary, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def redact_sensitive_text(value: str) -> str:
    redacted = re.sub(
        r"(?i)(postgres(?:ql)?(?:\+\w+)?://)[^\s\"']+",
        r"\1[REDACTED]",
        value,
    )
    redacted = re.sub(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9_-]+\b", "[REDACTED_KEY]", redacted)
    redacted = re.sub(
        r"(?i)((?:secret|password|token|api[_-]?key)\s*[=:]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted


def _frontend_binary(name: str) -> str:
    suffix = ".cmd" if os.name == "nt" else ""
    path = FRONTEND_ROOT / "node_modules" / ".bin" / f"{name}{suffix}"
    if not path.is_file():
        raise RuntimeError(
            f"frontend dependency binary is missing: {path.relative_to(PROJECT_ROOT)}"
        )
    return str(path)


def _required_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"required executable is unavailable: {name}")
    return executable


def _version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"could not read version from {Path(executable).name}")
    return redact_sensitive_text(completed.stdout.strip())


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if completed.returncode != 0:
        message = redact_sensitive_text(completed.stderr.strip())
        raise RuntimeError(f"git {' '.join(arguments)} failed: {message}")
    return completed.stdout.strip()


def _add_match(
    counts: dict[str, int],
    key: str,
    pattern: str,
    output: str,
) -> None:
    match = re.search(pattern, output)
    if match is not None:
        counts[key] = int(match.group(1))


def _timeout_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the resource-safe local release gate and optionally record evidence."
    )
    parser.add_argument(
        "--write-evidence",
        nargs="?",
        type=Path,
        const=DEFAULT_EVIDENCE_PATH,
        help="Write JSON evidence after a clean, passing run.",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="List the serial checks without executing them.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
