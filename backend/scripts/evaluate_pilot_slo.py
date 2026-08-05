import argparse
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.operational_slo import (
    evaluate_request_logs,
    load_pilot_slo_config,
    render_slo_markdown,
)
from app.evaluation.public_benchmark.storage import atomic_write_bytes, atomic_write_json

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_CONFIG_PATH = BACKEND_ROOT / "operations" / "pilot_slo.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / ".codex-runtime" / "pilot-slo-report.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate a bounded JSONL export of structured production request logs."
    )
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument(
        "--as-of",
        help="Timezone-aware ISO-8601 end of the observation window; defaults to now.",
    )
    arguments = parser.parse_args()
    evaluated_at = (
        datetime.fromisoformat(arguments.as_of.replace("Z", "+00:00"))
        if arguments.as_of
        else datetime.now(UTC)
    )
    config = load_pilot_slo_config(arguments.config)
    report = evaluate_request_logs(
        arguments.logs,
        config=config,
        evaluated_at=evaluated_at,
    )
    atomic_write_json(
        PROJECT_ROOT,
        arguments.report,
        report.model_dump(mode="json"),
    )
    markdown_path = arguments.report.with_suffix(".md")
    atomic_write_bytes(
        PROJECT_ROOT,
        markdown_path,
        render_slo_markdown(report).encode("utf-8"),
    )
    print(
        f"status={report.status} requests={report.request_events} "
        f"availability={report.availability} latency_p95_ms={report.latency_p95_ms} "
        f"report={arguments.report}"
    )
    if report.status == "failed":
        raise SystemExit(1)
    if report.status == "insufficient_data":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
