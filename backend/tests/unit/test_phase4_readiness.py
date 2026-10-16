from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.domain.controlled_operations import OPERATIONS
from app.evaluation.phase4_operations import latency_summary, simulated_reopen_summary
from app.evaluation.phase4_readiness import assess_development, proposed_action_types

ROOT = Path(__file__).resolve().parents[2] / "evaluations" / "case_resolution_v2_phase4"


def test_readiness_never_opens_holdout_or_invents_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.open
    paths: list[str] = []

    def guarded(path: Path, *args: Any, **kwargs: Any) -> Any:
        assert "holdout" not in str(path)
        paths.append(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    report = assess_development(ROOT)
    assert report["gate"] == "blocked"
    assert report["development_cases"] == 24
    assert report["cases_with_unavailable_actions"] == 0
    assert report["cases_with_missing_business_values"] == 0
    assert not report["unavailable_action_names"]
    assert report["provider_calls"] == 0
    assert not report["holdout_executed"]
    assert paths


def test_inventory_is_proposal_capability_not_generic_gateway_acceptance() -> None:
    assert proposed_action_types() == {
        "issue_refund",
        "reverse_duplicate_charge",
        "start_verified_recovery",
        "apply_service_correction",
        "request_information",
        *OPERATIONS,
    }
    assert "refund_course_fee" in proposed_action_types()


@pytest.mark.parametrize("samples", [[], [1.0], [1.0] * 99])
def test_tiny_samples_never_become_latency_percentiles(samples: list[float]) -> None:
    report = latency_summary(samples)
    assert report["p95_ms"] is None
    assert report["p50_ms"] is None
    assert report["samples"] == len(samples)


def test_latency_keeps_failures_when_caller_supplies_all_attempts() -> None:
    report = latency_summary([float(x) for x in range(1, 101)])
    assert (report["p50_ms"], report["p90_ms"], report["p95_ms"]) == (50, 90, 95)
    with pytest.raises(ValueError):
        latency_summary([1], minimum=1)


@pytest.mark.parametrize("value", [-1.0, float("inf"), float("nan")])
def test_invalid_latency_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        latency_summary([value])


@pytest.mark.parametrize("days", [7, 30])
def test_reopen_denominator_requires_full_followup(days: int) -> None:
    at = datetime(2026, 10, 14, tzinfo=UTC)
    early = simulated_reopen_summary(
        completed_at=at,
        reopened_at=at + timedelta(days=1),
        followed_until=at + timedelta(days=days, microseconds=-1),
        days=days,
    )
    assert early["denominator"] == 0
    assert early["value"] is None
    boundary = simulated_reopen_summary(
        completed_at=at,
        reopened_at=at + timedelta(days=days),
        followed_until=at + timedelta(days=days),
        days=days,
    )
    assert boundary["numerator"] == boundary["denominator"] == 1
    assert boundary["profile"] == "simulated_time_replay"


def test_followup_excludes_late_reopen_and_rejects_bad_chronology() -> None:
    at = datetime(2026, 10, 14, tzinfo=UTC)
    report = simulated_reopen_summary(
        completed_at=at,
        reopened_at=at + timedelta(days=8),
        followed_until=at + timedelta(days=30),
        days=7,
    )
    assert report["numerator"] == 0 and report["denominator"] == 1
    with pytest.raises(ValueError):
        simulated_reopen_summary(
            completed_at=at,
            reopened_at=at - timedelta(seconds=1),
            followed_until=at + timedelta(days=30),
            days=30,
        )
