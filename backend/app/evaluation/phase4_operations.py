"""Small operational summaries; no oracle correctness inferred from HTTP success."""

import math
from datetime import datetime, timedelta
from typing import Any


def latency_summary(samples_ms: list[float], *, minimum: int = 100) -> dict[str, Any]:
    if minimum < 100 or any(not math.isfinite(x) or x < 0 for x in samples_ms):
        raise ValueError("Invalid latency data or weakened minimum sample threshold")
    ordered = sorted(samples_ms)
    enough = len(ordered) >= minimum
    return dict(
        samples=len(ordered),
        minimum_samples=minimum,
        p50_ms=ordered[math.ceil(0.50 * len(ordered)) - 1] if enough else None,
        p90_ms=ordered[math.ceil(0.90 * len(ordered)) - 1] if enough else None,
        p95_ms=ordered[math.ceil(0.95 * len(ordered)) - 1] if enough else None,
        reason=None if enough else "insufficient_samples",
        method="nearest_rank",
    )


def simulated_reopen_summary(
    *, completed_at: datetime, reopened_at: datetime | None, followed_until: datetime, days: int
) -> dict[str, Any]:
    """One linked lifecycle; callers must validate scope and original-resolution linkage."""
    dates = [completed_at, followed_until] + ([reopened_at] if reopened_at else [])
    if days not in {7, 30} or any(value.utcoffset() is None for value in dates):
        raise ValueError("Require an aware simulated 7/30-day window")
    if followed_until < completed_at or (
        reopened_at is not None and not completed_at <= reopened_at <= followed_until
    ):
        raise ValueError("Invalid follow-up chronology")
    end = completed_at + timedelta(days=days)
    eligible = int(followed_until >= end)
    numerator = int(bool(eligible and reopened_at is not None and reopened_at <= end))
    return dict(
        profile="simulated_time_replay",
        days=days,
        numerator=numerator,
        denominator=eligible,
        value=numerator / eligible if eligible else None,
    )
