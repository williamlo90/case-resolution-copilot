import json
from pathlib import Path

import pytest

import app.evaluation.wave1_rag_runtime as rag_runtime
from app.evaluation.wave1_rag_contract import load_wave1_rag_fixture
from app.evaluation.wave1_rag_observability import JsonlRagEventSink
from app.evaluation.wave1_rag_runtime import run_wave1_rag_evaluation


def _fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "evaluations" / "wave1_rag" / "fixture.json"


def test_wave1_rag_fixture_runs_without_credentials_and_passes_source_gate() -> None:
    fixture = load_wave1_rag_fixture(_fixture_path())

    report = run_wave1_rag_evaluation(fixture=fixture)

    assert report.credential_free is True
    assert report.metrics.cases == 10
    assert report.metrics.runtime_failure_count == 0
    assert report.metrics.status_accuracy == 1.0
    assert report.metrics.source_hit_rate_at_3 == 1.0
    assert report.metrics.source_recall_at_3 == 1.0
    assert report.metrics.gate_passed


def test_wave1_rag_events_exclude_queries_content_and_sensitive_values(
    tmp_path: Path,
) -> None:
    fixture = load_wave1_rag_fixture(_fixture_path())
    event_path = tmp_path / "rag-events.jsonl"

    run_wave1_rag_evaluation(
        fixture=fixture,
        event_sink=JsonlRagEventSink(event_path),
        run_id="unit-wave1",
    )

    payload = event_path.read_text(encoding="utf-8")
    events = [json.loads(line) for line in payload.splitlines()]
    assert len(events) == len(fixture.cases)
    assert all("latency_ms" in event for event in events)
    assert all("query" not in event for event in events)
    assert all("source_content" not in event for event in events)
    assert "same invoice charge appears twice" not in payload.lower()
    assert "raw provider payloads" not in payload.lower()


def test_wave1_rag_report_keeps_runtime_failures_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_wave1_rag_fixture(_fixture_path())

    def fail_workspace(case: object) -> None:
        del case
        raise RuntimeError("sensitive failure detail")

    monkeypatch.setattr(rag_runtime, "benchmark_workspace", fail_workspace)

    report = run_wave1_rag_evaluation(fixture=fixture)

    assert report.metrics.gate_passed is False
    assert report.metrics.runtime_failure_count == len(fixture.cases)
    assert "runtime_failures" in report.metrics.gate_failures
    serialized = report.model_dump_json()
    assert "RuntimeError" in serialized
    assert "sensitive failure detail" not in serialized
