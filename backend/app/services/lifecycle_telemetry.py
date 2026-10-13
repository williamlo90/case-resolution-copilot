"""Structured stage timings; never log provider payloads or customer content."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_current: ContextVar[tuple[str, str] | None] = ContextVar("lifecycle_identity", default=None)


class LifecycleSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correlation_id: str = Field(min_length=1, max_length=128)
    subject_id: str = Field(min_length=1, max_length=128)
    stage: Literal[
        "db",
        "tool",
        "provider",
        "verification",
        "decision",
        "retrieval",
        "queue_wait",
        "worker",
        "manual_wait",
        "intake",
        "end_to_end",
    ]
    duration_ms: float = Field(ge=0, allow_inf_nan=False)
    outcome: Literal["completed", "failed"]


@contextmanager
def stage_span(
    correlation_id: str,
    subject_id: str,
    stage: Literal[
        "db",
        "tool",
        "provider",
        "verification",
        "decision",
        "retrieval",
        "queue_wait",
        "worker",
        "manual_wait",
        "intake",
        "end_to_end",
    ],
) -> Iterator[None]:
    # Validate identity before work, not only when emitting a result.
    identity = LifecycleSpan(
        correlation_id=correlation_id,
        subject_id=subject_id,
        stage=stage,
        duration_ms=0,
        outcome="completed",
    )
    token = _current.set((correlation_id, subject_id))
    started = perf_counter()
    outcome: Literal["completed", "failed"] = "completed"
    try:
        yield
    except Exception:
        outcome = "failed"
        raise
    finally:
        event = identity.model_copy(
            update={"duration_ms": (perf_counter() - started) * 1000, "outcome": outcome}
        )
        _current.reset(token)
        emit_span(event)


def emit_span(event: LifecycleSpan) -> None:
    logging.getLogger(__name__).info("case.lifecycle_stage", extra=event.model_dump())


@contextmanager
def provider_span() -> Iterator[None]:
    identity = _current.get()
    if identity is None:
        # Standalone provider utilities have no case/request identity.
        yield
    else:
        with stage_span(*identity, "provider"):
            yield
