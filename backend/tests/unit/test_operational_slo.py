import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.evaluation.operational_slo import (
    PilotSloConfig,
    RequestLogEvent,
    evaluate_request_logs,
    render_slo_markdown,
)
from app.logging import JsonFormatter

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def test_slo_evaluator_passes_bounded_window_without_exporting_request_details(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "requests.jsonl"
    _write_logs(
        log_path,
        [_event(status_code=200, duration_ms=100, offset_minutes=index) for index in range(10)],
    )

    report = evaluate_request_logs(
        log_path,
        config=_config(minimum_requests=10),
        evaluated_at=NOW,
    )

    assert report.status == "passed"
    assert report.availability == 1.0
    assert report.latency_p95_ms == 100
    serialized = report.model_dump_json()
    assert "/api/cases/CS-SECRET" not in serialized
    assert "corr-secret" not in serialized
    assert "Source SHA-256" in render_slo_markdown(report)


def test_slo_evaluator_reports_insufficient_data_honestly(tmp_path: Path) -> None:
    log_path = tmp_path / "requests.jsonl"
    _write_logs(log_path, [_event(status_code=200, duration_ms=50)])

    report = evaluate_request_logs(
        log_path,
        config=_config(minimum_requests=2),
        evaluated_at=NOW,
    )

    assert report.status == "insufficient_data"
    assert {objective.status for objective in report.objectives} == {"insufficient_data"}


def test_slo_evaluator_fails_availability_and_latency_objectives(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "requests.jsonl"
    _write_logs(
        log_path,
        [
            _event(status_code=200, duration_ms=100),
            _event(status_code=503, duration_ms=900),
        ],
    )

    report = evaluate_request_logs(
        log_path,
        config=_config(
            minimum_requests=2,
            availability_target=0.99,
            latency_p95_target_ms=500,
        ),
        evaluated_at=NOW,
    )

    assert report.status == "failed"
    assert report.availability == 0.5
    assert report.latency_p95_ms == 900
    assert [objective.status for objective in report.objectives] == [
        "failed",
        "failed",
    ]


def test_slo_evaluator_excludes_health_old_and_unrelated_events(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "requests.jsonl"
    _write_logs(
        log_path,
        [
            _event(status_code=200, duration_ms=100),
            _event(
                status_code=500,
                duration_ms=5000,
                path="/api/health/ready",
            ),
            _event(
                status_code=500,
                duration_ms=5000,
                timestamp=NOW - timedelta(days=8),
            ),
            {
                "timestamp": NOW.isoformat(),
                "logger": "app.main",
                "message": "application_started",
            },
        ],
    )

    report = evaluate_request_logs(
        log_path,
        config=_config(minimum_requests=1),
        evaluated_at=NOW,
    )

    assert report.status == "passed"
    assert report.request_events == 1
    assert report.ignored_events == 3


def test_slo_evaluator_rejects_invalid_json_and_oversized_input(
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid structured log JSON"):
        evaluate_request_logs(
            invalid,
            config=_config(),
            evaluated_at=NOW,
        )

    oversized = tmp_path / "oversized.jsonl"
    oversized.write_text("x" * 1025, encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds 1024 bytes"):
        evaluate_request_logs(
            oversized,
            config=_config(maximum_log_bytes=1024),
            evaluated_at=NOW,
        )


def test_json_formatter_emits_an_event_accepted_by_slo_parser() -> None:
    record = logging.LogRecord(
        name="app.api.middleware",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.method = "GET"
    record.path = "/api/cases"
    record.status_code = 200
    record.duration_ms = 125.5
    formatted = JsonFormatter().format(record)

    parsed = RequestLogEvent.model_validate_json(formatted)

    assert parsed.method == "GET"
    assert parsed.status_code == 200
    assert parsed.duration_ms == 125.5


def test_json_formatter_redacts_sensitive_extras_and_unstructured_text() -> None:
    try:
        raise RuntimeError("private provider response")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="app.security",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Customer email alice@example.com failed with token abc",
        args=(),
        exc_info=exc_info,
    )
    record.email = "alice@example.com"
    record.correlation_id = "corr_safe"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "unstructured_log_message_redacted"
    assert payload["email"] == "[REDACTED]"
    assert payload["correlation_id"] == "corr_safe"
    assert payload["exception_type"] == "RuntimeError"
    assert "alice@example.com" not in json.dumps(payload)
    assert "private provider response" not in json.dumps(payload)


def _config(
    *,
    minimum_requests: int = 1,
    availability_target: float = 0.9,
    latency_p95_target_ms: float = 1000,
    maximum_log_bytes: int = 1024 * 1024,
) -> PilotSloConfig:
    return PilotSloConfig(
        schema_version="pilot-slo-config-v1",
        window_hours=24 * 7,
        minimum_requests=minimum_requests,
        availability_target=availability_target,
        latency_p95_target_ms=latency_p95_target_ms,
        maximum_log_bytes=maximum_log_bytes,
        maximum_request_events=100,
        excluded_paths=["/api/health/live", "/api/health/ready"],
    )


def _event(
    *,
    status_code: int,
    duration_ms: float,
    offset_minutes: int = 0,
    path: str = "/api/cases/CS-SECRET",
    timestamp: datetime | None = None,
) -> dict[str, object]:
    return {
        "timestamp": (timestamp or NOW - timedelta(minutes=offset_minutes)).isoformat(),
        "level": "INFO",
        "logger": "app.api.middleware",
        "message": "request_completed",
        "correlation_id": "corr-secret",
        "method": "GET",
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }


def _write_logs(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )
