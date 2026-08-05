import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.evaluation.public_benchmark.storage import sha256_file

SloStatus = Literal["passed", "failed", "insufficient_data"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PilotSloConfig(StrictModel):
    schema_version: Literal["pilot-slo-config-v1"]
    window_hours: int = Field(ge=1, le=24 * 31)
    minimum_requests: int = Field(ge=1, le=1_000_000)
    availability_target: float = Field(gt=0, le=1)
    latency_p95_target_ms: float = Field(gt=0, le=120_000)
    maximum_log_bytes: int = Field(ge=1024, le=1024 * 1024 * 1024)
    maximum_request_events: int = Field(ge=1, le=5_000_000)
    excluded_paths: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("excluded_paths")
    @classmethod
    def validate_excluded_paths(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("SLO excluded paths must be unique.")
        if any(not path.startswith("/") or len(path) > 500 for path in value):
            raise ValueError("SLO excluded paths must be bounded absolute API paths.")
        return value


class RequestLogEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: datetime
    logger: Literal["app.api.middleware"]
    message: Literal["request_completed"]
    method: str = Field(pattern=r"^[A-Z]{3,10}$")
    path: str = Field(min_length=1, max_length=2000)
    status_code: int = Field(ge=100, le=599)
    duration_ms: float = Field(ge=0, le=3_600_000)

    @model_validator(mode="after")
    def require_aware_timestamp(self) -> Self:
        if self.timestamp.utcoffset() is None:
            raise ValueError("Request log timestamps must be timezone-aware.")
        return self


class SloObjectiveResult(StrictModel):
    name: Literal["availability", "latency_p95"]
    status: SloStatus
    observed: float | None
    target: float
    comparison: Literal["greater_than_or_equal", "less_than_or_equal"]


class PilotSloReport(StrictModel):
    schema_version: Literal["pilot-slo-report-v1"] = "pilot-slo-report-v1"
    evaluated_at: datetime
    window_started_at: datetime
    window_ended_at: datetime
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_bytes: int = Field(ge=0)
    request_events: int = Field(ge=0)
    successful_or_client_error_events: int = Field(ge=0)
    server_error_events: int = Field(ge=0)
    ignored_events: int = Field(ge=0)
    availability: float | None = Field(default=None, ge=0, le=1)
    latency_p95_ms: float | None = Field(default=None, ge=0)
    objectives: list[SloObjectiveResult] = Field(min_length=2, max_length=2)
    status: SloStatus
    interpretation: str = Field(min_length=1, max_length=1000)


def load_pilot_slo_config(path: Path) -> PilotSloConfig:
    if not path.is_file():
        raise ValueError("Pilot SLO configuration is required.")
    return PilotSloConfig.model_validate_json(path.read_text(encoding="utf-8"))


def evaluate_request_logs(
    log_path: Path,
    *,
    config: PilotSloConfig,
    evaluated_at: datetime,
) -> PilotSloReport:
    if evaluated_at.utcoffset() is None:
        raise ValueError("SLO evaluation time must be timezone-aware.")
    if not log_path.is_file():
        raise ValueError("Structured request log file is required.")
    source_bytes = log_path.stat().st_size
    if source_bytes > config.maximum_log_bytes:
        raise ValueError(f"Structured request log exceeds {config.maximum_log_bytes} bytes.")
    window_started_at = evaluated_at - timedelta(hours=config.window_hours)
    request_count = 0
    server_errors = 0
    durations: list[float] = []
    ignored_events = 0
    with log_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid structured log JSON at line {line_number}.") from exc
            if not isinstance(raw, dict):
                raise ValueError(f"Structured log line {line_number} must be an object.")
            if (
                raw.get("logger") != "app.api.middleware"
                or raw.get("message") != "request_completed"
            ):
                ignored_events += 1
                continue
            try:
                event = RequestLogEvent.model_validate(raw)
            except Exception as exc:
                raise ValueError(
                    f"Invalid request-completed event at line {line_number}: {exc}"
                ) from exc
            if event.path in config.excluded_paths:
                ignored_events += 1
                continue
            if not (window_started_at <= event.timestamp <= evaluated_at):
                ignored_events += 1
                continue
            request_count += 1
            if request_count > config.maximum_request_events:
                raise ValueError(
                    "Structured request log exceeds the configured request event limit."
                )
            server_errors += event.status_code >= 500
            durations.append(event.duration_ms)

    non_server_errors = request_count - server_errors
    availability = non_server_errors / request_count if request_count else None
    latency_p95 = _percentile_nearest_rank(
        durations,
        percentile=0.95,
    )
    enough_data = request_count >= config.minimum_requests
    availability_status = _objective_status(
        enough_data=enough_data,
        passed=(availability is not None and availability >= config.availability_target),
    )
    latency_status = _objective_status(
        enough_data=enough_data,
        passed=(latency_p95 is not None and latency_p95 <= config.latency_p95_target_ms),
    )
    objectives = [
        SloObjectiveResult(
            name="availability",
            status=availability_status,
            observed=availability,
            target=config.availability_target,
            comparison="greater_than_or_equal",
        ),
        SloObjectiveResult(
            name="latency_p95",
            status=latency_status,
            observed=latency_p95,
            target=config.latency_p95_target_ms,
            comparison="less_than_or_equal",
        ),
    ]
    overall_status = _overall_status(objectives)
    return PilotSloReport(
        evaluated_at=evaluated_at,
        window_started_at=window_started_at,
        window_ended_at=evaluated_at,
        source_sha256=sha256_file(log_path),
        source_bytes=source_bytes,
        request_events=request_count,
        successful_or_client_error_events=non_server_errors,
        server_error_events=server_errors,
        ignored_events=ignored_events,
        availability=availability,
        latency_p95_ms=latency_p95,
        objectives=objectives,
        status=overall_status,
        interpretation=_interpretation(
            status=overall_status,
            request_count=request_count,
            minimum_requests=config.minimum_requests,
        ),
    )


def render_slo_markdown(report: PilotSloReport) -> str:
    availability = (
        f"{report.availability:.5f}" if report.availability is not None else "not available"
    )
    latency = (
        f"{report.latency_p95_ms:.2f} ms" if report.latency_p95_ms is not None else "not available"
    )
    lines = [
        "# Pilot SLO Evaluation",
        "",
        f"- Status: `{report.status}`",
        f"- Window: `{report.window_started_at.isoformat()}` to "
        f"`{report.window_ended_at.isoformat()}`",
        f"- Request events: `{report.request_events}`",
        f"- Availability: `{availability}`",
        f"- Latency p95: `{latency}`",
        f"- Source SHA-256: `{report.source_sha256}`",
        "",
        "## Objectives",
        "",
        "| Objective | Status | Observed | Target |",
        "| --- | --- | ---: | ---: |",
    ]
    for objective in report.objectives:
        observed = (
            f"{objective.observed:.5f}" if objective.observed is not None else "not available"
        )
        comparison = ">=" if objective.comparison == "greater_than_or_equal" else "<="
        lines.append(
            f"| {objective.name} | {objective.status} | {observed} | "
            f"{comparison} {objective.target} |"
        )
    lines.extend(["", report.interpretation, ""])
    return "\n".join(lines)


def _percentile_nearest_rank(
    values: list[float],
    *,
    percentile: float,
) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _objective_status(*, enough_data: bool, passed: bool) -> SloStatus:
    if not enough_data:
        return "insufficient_data"
    return "passed" if passed else "failed"


def _overall_status(objectives: list[SloObjectiveResult]) -> SloStatus:
    statuses = {objective.status for objective in objectives}
    if "insufficient_data" in statuses:
        return "insufficient_data"
    return "failed" if "failed" in statuses else "passed"


def _interpretation(
    *,
    status: SloStatus,
    request_count: int,
    minimum_requests: int,
) -> str:
    if status == "insufficient_data":
        return (
            f"The observation contains {request_count} eligible request(s); at least "
            f"{minimum_requests} are required before an SLO verdict."
        )
    if status == "failed":
        return (
            "One or more pilot SLO objectives failed. Investigate correlated production logs "
            "before widening the pilot."
        )
    return (
        "Both pilot HTTP objectives passed for this bounded observation window. This report does "
        "not replace alert delivery, incident ownership, or provider-specific health evidence."
    )
