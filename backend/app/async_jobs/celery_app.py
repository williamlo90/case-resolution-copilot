from collections.abc import Callable
from typing import TYPE_CHECKING

from app.async_jobs.runner import (
    AsyncDeliveryUnavailable,
    AsyncJobRunner,
    build_async_job_runner,
)
from app.async_jobs.settings import AsyncJobSettings
from app.config import Settings, get_settings

if TYPE_CHECKING:
    from celery import Celery, Task

HEALTH_TASK = "case_resolution.async_jobs.health"
INBOX_DRAIN_TASK = "case_resolution.async_jobs.inbox_sync.drain"
INBOX_STATUS_TASK = "case_resolution.async_jobs.inbox_sync.status"
INBOX_REPROCESS_TASK = "case_resolution.async_jobs.inbox_sync.reprocess"
POLICY_DRAIN_TASK = "case_resolution.async_jobs.policy_index.drain"
POLICY_STATUS_TASK = "case_resolution.async_jobs.policy_index.status"
POLICY_REPROCESS_TASK = "case_resolution.async_jobs.policy_index.reprocess"

RunnerFactory = Callable[[], AsyncJobRunner]


def create_celery_app(
    *,
    app_settings: Settings | None = None,
    job_settings: AsyncJobSettings | None = None,
    runner_factory: RunnerFactory | None = None,
) -> "Celery":
    try:
        from celery import Celery
    except ImportError as exc:
        raise RuntimeError(
            "Celery delivery requires the celery[redis] backend dependency."
        ) from exc

    resolved_app_settings = app_settings or get_settings()
    resolved_job_settings = job_settings or AsyncJobSettings()
    celery_app = Celery(
        "case_resolution_async_jobs",
        broker=resolved_job_settings.broker(),
        backend=resolved_job_settings.result_backend(),
    )
    celery_app.conf.update(
        task_default_queue=resolved_job_settings.queue_name,
        task_routes={
            task_name: {"queue": resolved_job_settings.queue_name} for task_name in _TASK_NAMES
        },
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        # PostgreSQL leases recover abandoned work; broker poison-message loops do not.
        task_reject_on_worker_lost=False,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
        task_soft_time_limit=resolved_job_settings.task_soft_time_limit_seconds,
        task_time_limit=resolved_job_settings.task_time_limit_seconds,
        result_expires=resolved_job_settings.result_expires_seconds,
        beat_schedule=_beat_schedule(resolved_app_settings, resolved_job_settings),
    )
    register_tasks(
        celery_app,
        runner_factory=runner_factory
        or (
            lambda: build_async_job_runner(
                app_settings=resolved_app_settings,
                job_settings=resolved_job_settings,
            )
        ),
        max_retries=resolved_job_settings.delivery_max_retries,
    )
    return celery_app


def register_tasks(
    celery_app: "Celery",
    *,
    runner_factory: RunnerFactory,
    max_retries: int,
) -> None:
    retry_options = {
        "autoretry_for": (AsyncDeliveryUnavailable,),
        "retry_kwargs": {"max_retries": max_retries},
        "retry_backoff": 2,
        "retry_backoff_max": 60,
        "retry_jitter": True,
    }

    @celery_app.task(bind=True, name=HEALTH_TASK)  # type: ignore[untyped-decorator]
    def health(task: "Task") -> dict[str, str | int | bool]:
        return runner_factory().health(worker_id=_worker_id(task))

    @celery_app.task(  # type: ignore[untyped-decorator]
        bind=True, name=INBOX_DRAIN_TASK, **retry_options
    )
    def drain_inbox(task: "Task") -> dict[str, str | int | None]:
        return runner_factory().drain_inbox(worker_id=_worker_id(task)).as_payload()

    @celery_app.task(  # type: ignore[untyped-decorator]
        bind=True, name=POLICY_DRAIN_TASK, **retry_options
    )
    def drain_policy_index(task: "Task") -> dict[str, str | int | None]:
        return runner_factory().drain_policy_index(worker_id=_worker_id(task)).as_payload()

    @celery_app.task(  # type: ignore[untyped-decorator]
        bind=True, name=INBOX_STATUS_TASK, **retry_options
    )
    def inbox_status(
        task: "Task", organization_id: str, job_id: str
    ) -> dict[str, str | int | None]:
        return (
            runner_factory()
            .inbox_job_status(
                worker_id=_worker_id(task),
                organization_id=organization_id,
                job_id=job_id,
            )
            .as_payload()
        )

    @celery_app.task(  # type: ignore[untyped-decorator]
        bind=True, name=POLICY_STATUS_TASK, **retry_options
    )
    def policy_status(
        task: "Task", organization_id: str, job_id: str
    ) -> dict[str, str | int | None]:
        return (
            runner_factory()
            .policy_job_status(
                worker_id=_worker_id(task),
                organization_id=organization_id,
                job_id=job_id,
            )
            .as_payload()
        )

    @celery_app.task(  # type: ignore[untyped-decorator]
        bind=True, name=INBOX_REPROCESS_TASK, **retry_options
    )
    def reprocess_inbox(
        task: "Task", organization_id: str, job_id: str
    ) -> dict[str, str | int | None]:
        return (
            runner_factory()
            .reprocess_inbox(
                worker_id=_worker_id(task),
                organization_id=organization_id,
                job_id=job_id,
            )
            .as_payload()
        )

    @celery_app.task(  # type: ignore[untyped-decorator]
        bind=True, name=POLICY_REPROCESS_TASK, **retry_options
    )
    def reprocess_policy(
        task: "Task", organization_id: str, job_id: str
    ) -> dict[str, str | int | None]:
        return (
            runner_factory()
            .reprocess_policy_index(
                worker_id=_worker_id(task),
                organization_id=organization_id,
                job_id=job_id,
            )
            .as_payload()
        )


def _worker_id(task: "Task") -> str:
    request_id = getattr(task.request, "id", None)
    return f"celery:{request_id or 'unknown'}"


def _beat_schedule(
    app_settings: Settings,
    job_settings: AsyncJobSettings,
) -> dict[str, dict[str, object]]:
    schedule: dict[str, dict[str, object]] = {}
    if app_settings.inbox_scheduled_sync_enabled:
        schedule["drain-durable-inbox-sync"] = {
            "task": INBOX_DRAIN_TASK,
            "schedule": float(job_settings.inbox_drain_interval_seconds),
        }
    if app_settings.policy_indexing_enabled:
        schedule["drain-durable-policy-index"] = {
            "task": POLICY_DRAIN_TASK,
            "schedule": float(job_settings.policy_index_interval_seconds),
        }
    return schedule


_TASK_NAMES = (
    HEALTH_TASK,
    INBOX_DRAIN_TASK,
    INBOX_STATUS_TASK,
    INBOX_REPROCESS_TASK,
    POLICY_DRAIN_TASK,
    POLICY_STATUS_TASK,
    POLICY_REPROCESS_TASK,
)
