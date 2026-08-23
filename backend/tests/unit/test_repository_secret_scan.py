import subprocess
from pathlib import Path

import pytest

from scripts.check_repository_secrets import repository_files, scan_text


def test_secret_scan_reports_rule_and_path_without_secret_value() -> None:
    secret = "sk_live_" + ("a" * 32)

    findings = scan_text("config/example.txt", f"CLERK_SECRET_KEY={secret}")

    assert [(finding.path, finding.rule) for finding in findings] == [
        ("config/example.txt", "clerk_secret")
    ]
    assert all(secret not in repr(finding) for finding in findings)


def test_secret_scan_allows_documented_placeholders() -> None:
    findings = scan_text(
        ".env.example",
        "\n".join(
            (
                "SUPPORT_COPILOT_DATABASE_URL=replace_with_neon_database_url",
                "SUPPORT_COPILOT_CLERK_SECRET_KEY=replace_with_clerk_secret_key",
            )
        ),
    )

    assert findings == ()


def test_secret_scan_distinguishes_remote_database_password_from_local_fixture() -> None:
    remote = scan_text(
        "settings.txt",
        "DATABASE_URL=postgresql://service:high-entropy-value@db.example.com/app",
    )
    local = scan_text(
        ".env.example",
        "DATABASE_URL=postgresql://support_copilot:support_copilot@127.0.0.1:5432/app",
    )

    assert [(finding.path, finding.rule) for finding in remote] == [
        ("settings.txt", "database_url_with_password")
    ]
    assert local == ()


def test_secret_scan_includes_untracked_nonignored_repository_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed_command: list[str] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        observed_command.extend(command)
        assert cwd == tmp_path
        assert check is True
        assert capture_output is True
        return subprocess.CompletedProcess(command, 0, stdout=b"tracked.py\0new.py\0")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert repository_files(tmp_path) == (
        tmp_path / "tracked.py",
        tmp_path / "new.py",
    )
    assert observed_command == [
        "git",
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ]
