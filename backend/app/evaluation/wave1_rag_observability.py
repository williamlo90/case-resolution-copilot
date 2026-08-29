from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain.policies import EvidenceRetrievalStatus


class RagEvaluationEvent(BaseModel):
    """A bounded event that intentionally excludes queries and source content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["rag-evaluation-event-v1"] = "rag-evaluation-event-v1"
    timestamp: datetime
    event_name: Literal[
        "rag_evaluation_case_completed",
        "rag_evaluation_case_failed",
    ]
    run_id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    expected_status: EvidenceRetrievalStatus
    observed_status: EvidenceRetrievalStatus | None
    retrieved_source_ids: tuple[str, ...]
    latency_ms: float = Field(ge=0)
    error_code: str | None = Field(default=None, max_length=100)


class RagEventSink(Protocol):
    def emit(self, event: RagEvaluationEvent) -> None: ...


class JsonlRagEventSink:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        self._path = path

    def emit(self, event: RagEvaluationEvent) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")


def make_rag_event(
    *,
    run_id: str,
    case_id: str,
    expected_status: EvidenceRetrievalStatus,
    observed_status: EvidenceRetrievalStatus | None,
    retrieved_source_ids: tuple[str, ...],
    latency_ms: float,
    error_code: str | None,
    now: Callable[[], datetime] | None = None,
) -> RagEvaluationEvent:
    clock = now or (lambda: datetime.now(UTC))
    return RagEvaluationEvent(
        timestamp=clock(),
        event_name=(
            "rag_evaluation_case_failed"
            if error_code is not None
            else "rag_evaluation_case_completed"
        ),
        run_id=run_id,
        case_id=case_id,
        expected_status=expected_status,
        observed_status=observed_status,
        retrieved_source_ids=retrieved_source_ids,
        latency_ms=latency_ms,
        error_code=error_code,
    )
