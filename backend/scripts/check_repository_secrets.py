from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_TEXT_FILE_BYTES = 2_000_000
EXCLUDED_PATHS = frozenset(
    {
        "backend/scripts/check_repository_secrets.py",
        "backend/tests/unit/test_release_verification.py",
        "backend/tests/unit/test_repository_secret_scan.py",
    }
)
SECRET_PATTERNS = (
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "clerk_secret",
        re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{24,}\b"),
    ),
    (
        "openai_secret",
        re.compile(r"\bsk-proj-[A-Za-z0-9_-]{30,}\b"),
    ),
    (
        "github_token",
        re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{30,}\b"),
    ),
    (
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "database_url_with_password",
        re.compile(
            r"\bpostgres(?:ql)?(?:\+[a-z0-9_]+)?://"
            r"[^:\s/]+:[^@\s/]+@[^\s/'\"]+"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SecretFinding:
    path: str
    rule: str


def scan_text(path: str, text: str) -> tuple[SecretFinding, ...]:
    return tuple(
        SecretFinding(path=path, rule=rule)
        for rule, pattern in SECRET_PATTERNS
        if _contains_secret(rule, pattern, text)
    )


def _contains_secret(rule: str, pattern: re.Pattern[str], text: str) -> bool:
    if rule != "database_url_with_password":
        return pattern.search(text) is not None
    return any(
        not _safe_database_reference(match.group(0))
        for match in pattern.finditer(text)
    )


def _safe_database_reference(value: str) -> bool:
    credentials, host = value.rsplit("@", maxsplit=1)
    password = credentials.rsplit(":", maxsplit=1)[1].lower()
    hostname = host.split(":", maxsplit=1)[0].lower()
    return (
        "${" in value
        or password in {"pass", "password", "example", "support_copilot", "travelops"}
        or hostname in {"127.0.0.1", "localhost", "postgres"}
    )


def tracked_files(project_root: Path = PROJECT_ROOT) -> tuple[Path, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=project_root,
        check=True,
        capture_output=True,
    )
    return tuple(
        project_root / raw_path.decode("utf-8")
        for raw_path in completed.stdout.split(b"\0")
        if raw_path
    )


def scan_repository(
    project_root: Path = PROJECT_ROOT,
) -> tuple[SecretFinding, ...]:
    findings: list[SecretFinding] = []
    for path in tracked_files(project_root):
        relative_path = path.relative_to(project_root).as_posix()
        if relative_path in EXCLUDED_PATHS or path.stat().st_size > MAX_TEXT_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(relative_path, text))
    return tuple(findings)


def main() -> int:
    findings = scan_repository()
    if findings:
        print(f"status=failed findings={len(findings)}")
        for finding in findings:
            print(f"path={finding.path} rule={finding.rule}")
        return 1
    print("status=passed findings=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
