from contextlib import AbstractContextManager
from types import TracebackType
from typing import cast

import pytest

from app.async_jobs.runner import (
    AsyncDeliveryUnavailable,
    AsyncJobRunner,
)
from app.async_jobs.runtime import AsyncJobRuntime
from app.async_jobs.settings import AsyncJobSettings
from app.config import Settings
from app.domain.inbox import InboxSyncDrainResult
from app.domain.policy_indexing import PolicyIndexDrainResult
from app.runtime.inbox import InboxRuntime
from app.services.policy_indexing import PolicyIndexingService


class _InboxSync:
    def __init__(self) -> None:
        self.worker_id: str | None = None
        self.limit: int | None = None

    def drain(self, *, worker_id: str, limit: int) -> InboxSyncDrainResult:
        self.worker_id = worker_id
        self.limit = limit
        return InboxSyncDrainResult(
            claimed_jobs=1,
            completed_jobs=1,
            failed_jobs=0,
            imported_messages=4,
            duplicate_messages=2,
        )


class _Inbox:
    def __init__(self, sync: _InboxSync) -> None:
        self.sync = sync


class _PolicyIndexing:
    def __init__(self) -> None:
        self.worker_id: str | None = None

    def drain(self, *, worker_id: str) -> PolicyIndexDrainResult:
        self.worker_id = worker_id
        return PolicyIndexDrainResult(
            claimed_jobs=1,
            completed_jobs=0,
            failed_jobs=0,
            indexed_clauses=8,
            skipped_clauses=1,
        )


class _RuntimeContext:
    def __init__(self, runtime: AsyncJobRuntime) -> None:
        self.runtime = runtime
        self.closed = False

    def __enter__(self) -> AsyncJobRuntime:
        return self.runtime

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.closed = True


class _UnavailableContext:
    def __enter__(self) -> AsyncJobRuntime:
        raise OSError("Redis delivery reached a temporarily unavailable database runtime.")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


def _enabled_settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://unit:unit@127.0.0.1/unit",
        inbox_connections_enabled=True,
        inbox_scheduled_sync_enabled=True,
        inbox_scheduler_secret="x" * 32,
        policy_indexing_enabled=True,
        policy_index_scheduler_secret="y" * 32,
    )


def test_runner_drains_existing_services_with_bounded_limits() -> None:
    inbox_sync = _InboxSync()
    policy_indexing = _PolicyIndexing()
    runtime = AsyncJobRuntime(
        inbox=cast(InboxRuntime, _Inbox(inbox_sync)),
        policy_indexing=cast(PolicyIndexingService, policy_indexing),
    )
    contexts: list[_RuntimeContext] = []

    def runtime_factory() -> AbstractContextManager[AsyncJobRuntime]:
        context = _RuntimeContext(runtime)
        contexts.append(context)
        return context

    runner = AsyncJobRunner(
        runtime_factory=runtime_factory,
        app_settings=_enabled_settings(),
        job_settings=AsyncJobSettings(),
    )

    inbox = runner.drain_inbox(worker_id="celery:inbox-unit")
    policy = runner.drain_policy_index(worker_id="celery:policy-unit")

    assert inbox.as_payload() == {
        "capability": "inbox_sync",
        "state": "completed",
        "worker_id": "celery:inbox-unit",
        "job_id": None,
        "claimed_jobs": 1,
        "completed_jobs": 1,
        "failed_jobs": 0,
        "processed_items": 4,
        "duplicate_items": 2,
    }
    assert policy.processed_items == 8
    assert policy.duplicate_items == 1
    assert inbox_sync.limit == 1
    assert policy_indexing.worker_id == "celery:policy-unit"
    assert all(context.closed for context in contexts)


def test_runner_reports_disabled_capabilities_without_retrying() -> None:
    context = _RuntimeContext(AsyncJobRuntime(inbox=None, policy_indexing=None))
    runner = AsyncJobRunner(
        runtime_factory=lambda: context,
        app_settings=Settings(),
        job_settings=AsyncJobSettings(),
    )

    assert runner.drain_inbox(worker_id="celery:unit").state == "disabled"
    assert runner.drain_policy_index(worker_id="celery:unit").state == "disabled"


def test_runner_marks_only_transport_runtime_failures_as_retryable() -> None:
    runner = AsyncJobRunner(
        runtime_factory=lambda: _UnavailableContext(),
        app_settings=_enabled_settings(),
        job_settings=AsyncJobSettings(),
    )

    with pytest.raises(AsyncDeliveryUnavailable, match="OSError"):
        runner.drain_inbox(worker_id="celery:unit")


def test_health_surface_never_exposes_redis_credentials() -> None:
    job_settings = AsyncJobSettings(
        broker_url="rediss://worker:secret@redis.example.test:6380/0",
        result_backend_url="rediss://worker:other-secret@redis.example.test:6380/1",
    )
    runner = AsyncJobRunner(
        runtime_factory=lambda: _RuntimeContext(AsyncJobRuntime(inbox=None, policy_indexing=None)),
        app_settings=Settings(),
        job_settings=job_settings,
    )

    payload = runner.health(worker_id="celery:health-unit")

    assert payload["broker_scheme"] == "rediss"
    assert "secret" not in repr(payload)
    assert "redis.example.test" not in repr(payload)


def test_result_backend_defaults_to_the_broker_without_exposing_it() -> None:
    settings = AsyncJobSettings(broker_url="rediss://worker:secret@redis.example.test:6380/0")

    assert settings.result_backend() == settings.broker()
    assert "redis.example.test" not in repr(settings.safe_summary())


def test_durable_lease_outlives_the_celery_hard_limit() -> None:
    settings = AsyncJobSettings(
        task_soft_time_limit_seconds=100,
        task_time_limit_seconds=120,
        lease_safety_margin_seconds=30,
    )

    assert settings.lease_duration_seconds() == 150
    assert settings.safe_summary()["lease_duration_seconds"] == 150
