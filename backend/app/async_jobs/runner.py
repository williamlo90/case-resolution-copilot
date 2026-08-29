from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.exc import DBAPIError

from app.async_jobs.runtime import AsyncJobRuntime, build_async_job_runtime
from app.async_jobs.settings import AsyncJobSettings
from app.config import Settings, get_settings

TaskState = Literal[
    "healthy",
    "disabled",
    "idle",
    "completed",
    "requeued",
    "not_found",
    "pending",
    "running",
    "failed",
    "dead",
]
RuntimeFactory = Callable[[], AbstractContextManager[AsyncJobRuntime]]


class AsyncDeliveryUnavailable(RuntimeError):
    """A temporary delivery/runtime failure that Celery may retry finitely."""


@dataclass(frozen=True, slots=True)
class TaskOutcome:
    capability: str
    state: TaskState
    worker_id: str
    job_id: str | None = None
    claimed_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    processed_items: int = 0
    duplicate_items: int = 0

    def as_payload(self) -> dict[str, str | int | None]:
        return {
            "capability": self.capability,
            "state": self.state,
            "worker_id": self.worker_id,
            "job_id": self.job_id,
            "claimed_jobs": self.claimed_jobs,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "processed_items": self.processed_items,
            "duplicate_items": self.duplicate_items,
        }


class AsyncJobRunner:
    def __init__(
        self,
        *,
        runtime_factory: RuntimeFactory,
        app_settings: Settings,
        job_settings: AsyncJobSettings,
    ) -> None:
        self._runtime_factory = runtime_factory
        self._app_settings = app_settings
        self._job_settings = job_settings

    def health(self, *, worker_id: str) -> dict[str, str | int | bool]:
        return {
            "capability": "async_ingestion",
            "state": "healthy",
            "worker_id": worker_id,
            "inbox_enabled": self._app_settings.inbox_scheduled_sync_enabled,
            "policy_indexing_enabled": self._app_settings.policy_indexing_enabled,
            **self._job_settings.safe_summary(),
        }

    def drain_inbox(self, *, worker_id: str) -> TaskOutcome:
        def operation(runtime: AsyncJobRuntime) -> TaskOutcome:
            if runtime.inbox is None or not self._app_settings.inbox_scheduled_sync_enabled:
                return TaskOutcome("inbox_sync", "disabled", worker_id)
            result = runtime.inbox.sync.drain(
                worker_id=worker_id,
                limit=1,
            )
            return TaskOutcome(
                capability="inbox_sync",
                state="completed" if result.claimed_jobs else "idle",
                worker_id=worker_id,
                claimed_jobs=result.claimed_jobs,
                completed_jobs=result.completed_jobs,
                failed_jobs=result.failed_jobs,
                processed_items=result.imported_messages,
                duplicate_items=result.duplicate_messages,
            )

        return self._run(operation)

    def drain_policy_index(self, *, worker_id: str) -> TaskOutcome:
        def operation(runtime: AsyncJobRuntime) -> TaskOutcome:
            if runtime.policy_indexing is None:
                return TaskOutcome("policy_index", "disabled", worker_id)
            result = runtime.policy_indexing.drain(worker_id=worker_id)
            return TaskOutcome(
                capability="policy_index",
                state="completed" if result.claimed_jobs else "idle",
                worker_id=worker_id,
                claimed_jobs=result.claimed_jobs,
                completed_jobs=result.completed_jobs,
                failed_jobs=result.failed_jobs,
                processed_items=result.indexed_clauses,
                duplicate_items=result.skipped_clauses,
            )

        return self._run(operation)

    def inbox_job_status(
        self,
        *,
        worker_id: str,
        organization_id: str,
        job_id: str,
    ) -> TaskOutcome:
        def operation(runtime: AsyncJobRuntime) -> TaskOutcome:
            if runtime.inbox is None:
                return TaskOutcome("inbox_sync", "disabled", worker_id, job_id)
            job = runtime.inbox.sync.job_status(
                organization_public_id=organization_id,
                job_public_id=job_id,
            )
            if job is None:
                return TaskOutcome("inbox_sync", "not_found", worker_id, job_id)
            return TaskOutcome("inbox_sync", _job_state(job.status.value), worker_id, job_id)

        return self._run(operation)

    def policy_job_status(
        self,
        *,
        worker_id: str,
        organization_id: str,
        job_id: str,
    ) -> TaskOutcome:
        def operation(runtime: AsyncJobRuntime) -> TaskOutcome:
            if runtime.policy_indexing is None:
                return TaskOutcome("policy_index", "disabled", worker_id, job_id)
            job = runtime.policy_indexing.job_status(
                organization_public_id=organization_id,
                job_public_id=job_id,
            )
            if job is None:
                return TaskOutcome("policy_index", "not_found", worker_id, job_id)
            return TaskOutcome("policy_index", _job_state(job.status.value), worker_id, job_id)

        return self._run(operation)

    def reprocess_inbox(
        self,
        *,
        worker_id: str,
        organization_id: str,
        job_id: str,
    ) -> TaskOutcome:
        def operation(runtime: AsyncJobRuntime) -> TaskOutcome:
            if runtime.inbox is None:
                return TaskOutcome("inbox_sync", "disabled", worker_id, job_id)
            job = runtime.inbox.sync.reprocess(
                organization_public_id=organization_id,
                job_public_id=job_id,
            )
            state: TaskState = (
                "requeued" if job.status.value == "pending" else _job_state(job.status.value)
            )
            return TaskOutcome("inbox_sync", state, worker_id, job_id)

        return self._run(operation)

    def reprocess_policy_index(
        self,
        *,
        worker_id: str,
        organization_id: str,
        job_id: str,
    ) -> TaskOutcome:
        def operation(runtime: AsyncJobRuntime) -> TaskOutcome:
            if runtime.policy_indexing is None:
                return TaskOutcome("policy_index", "disabled", worker_id, job_id)
            job = runtime.policy_indexing.reprocess(
                organization_public_id=organization_id,
                job_public_id=job_id,
            )
            state: TaskState = (
                "requeued" if job.status.value == "pending" else _job_state(job.status.value)
            )
            return TaskOutcome("policy_index", state, worker_id, job_id)

        return self._run(operation)

    def _run(self, operation: Callable[[AsyncJobRuntime], TaskOutcome]) -> TaskOutcome:
        try:
            with self._runtime_factory() as runtime:
                return operation(runtime)
        except (DBAPIError, TimeoutError, OSError) as exc:
            raise AsyncDeliveryUnavailable(type(exc).__name__) from exc


def build_async_job_runner(
    *,
    app_settings: Settings | None = None,
    job_settings: AsyncJobSettings | None = None,
) -> AsyncJobRunner:
    resolved_app_settings = app_settings or get_settings()
    resolved_job_settings = job_settings or AsyncJobSettings()
    return AsyncJobRunner(
        runtime_factory=lambda: build_async_job_runtime(
            resolved_app_settings,
            resolved_job_settings,
        ),
        app_settings=resolved_app_settings,
        job_settings=resolved_job_settings,
    )


def _job_state(status: str) -> TaskState:
    states: dict[str, TaskState] = {
        "pending": "pending",
        "running": "running",
        "completed": "completed",
        "failed": "failed",
        "dead": "dead",
    }
    return states.get(status, "idle")
