import argparse
from pathlib import Path

from app.config import Settings
from app.evaluation.framework_validation import (
    markdown_report,
    run_framework_validation,
    validation_case_contract,
)
from app.evaluation.public_benchmark.storage import atomic_write_bytes, atomic_write_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one bounded case through the Wave 2 framework paths."
    )
    parser.add_argument(
        "--check-contract",
        action="store_true",
        help="Validate the frozen case contract without making provider calls.",
    )
    arguments = parser.parse_args()
    if arguments.check_contract:
        contract = validation_case_contract()
        print(f"case={contract['case_id']} synthetic=true approval_required=true provider_calls=0")
        return

    settings = Settings()
    api_key = settings.openai_secret()
    if not api_key:
        raise RuntimeError(
            "SUPPORT_COPILOT_OPENAI_API_KEY is required for live framework validation."
        )
    report = run_framework_validation(
        api_key=api_key,
        model=settings.openai_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )
    repo_root = Path(__file__).resolve().parents[2]
    evidence_root = repo_root / "docs" / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        repo_root,
        evidence_root / "framework-validation.json",
        report.model_dump(mode="json"),
    )
    atomic_write_bytes(
        repo_root,
        evidence_root / "framework-validation.md",
        markdown_report(report).encode("utf-8"),
    )
    print(
        f"case={report.synthetic_case_id} paths={len(report.paths)} "
        f"passed={report.passed} failed={report.failed} accepted={report.accepted}"
    )
    if not report.accepted:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
