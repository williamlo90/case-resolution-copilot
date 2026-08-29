from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

from app.async_jobs.celery_app import (
    HEALTH_TASK,
    INBOX_DRAIN_TASK,
    INBOX_REPROCESS_TASK,
    POLICY_DRAIN_TASK,
    create_celery_app,
    register_tasks,
)
from app.async_jobs.runner import AsyncJobRunner, TaskOutcome
from app.async_jobs.settings import AsyncJobSettings
from app.config import Settings


@dataclass(frozen=True, slots=True)
class _RegisteredTask:
    function: Callable[..., object]
    options: dict[str, object]


class _FakeCelery:
    def __init__(self) -> None:
        self.tasks: dict[str, _RegisteredTask] = {}

    def task(self, **options: object) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def decorator(function: Callable[..., object]) -> Callable[..., object]:
            name = cast(str, options["name"])
            self.tasks[name] = _RegisteredTask(function=function, options=options)
            return function

        return decorator


class _Runner:
    def health(self, *, worker_id: str) -> dict[str, str]:
        return {"worker_id": worker_id}

    def drain_inbox(self, *, worker_id: str) -> TaskOutcome:
        return TaskOutcome("inbox_sync", "idle", worker_id)

    def drain_policy_index(self, *, worker_id: str) -> TaskOutcome:
        return TaskOutcome("policy_index", "idle", worker_id)

    def inbox_job_status(self, *, worker_id: str, organization_id: str, job_id: str) -> TaskOutcome:
        del organization_id
        return TaskOutcome("inbox_sync", "pending", worker_id, job_id)

    def policy_job_status(
        self, *, worker_id: str, organization_id: str, job_id: str
    ) -> TaskOutcome:
        del organization_id
        return TaskOutcome("policy_index", "pending", worker_id, job_id)

    def reprocess_inbox(self, *, worker_id: str, organization_id: str, job_id: str) -> TaskOutcome:
        del organization_id
        return TaskOutcome("inbox_sync", "requeued", worker_id, job_id)

    def reprocess_policy_index(
        self, *, worker_id: str, organization_id: str, job_id: str
    ) -> TaskOutcome:
        del organization_id
        return TaskOutcome("policy_index", "requeued", worker_id, job_id)


def test_registered_delivery_tasks_have_finite_retry_contract() -> None:
    celery = _FakeCelery()
    runner = _Runner()

    register_tasks(
        cast(Any, celery),
        runner_factory=cast(Callable[[], AsyncJobRunner], lambda: runner),
        max_retries=4,
    )

    assert HEALTH_TASK in celery.tasks
    for task_name in (INBOX_DRAIN_TASK, POLICY_DRAIN_TASK, INBOX_REPROCESS_TASK):
        options = celery.tasks[task_name].options
        assert options["retry_kwargs"] == {"max_retries": 4}
        assert options["retry_backoff"] == 2
        assert options["retry_backoff_max"] == 60
        assert options["retry_jitter"] is True

    task = SimpleNamespace(request=SimpleNamespace(id="delivery-unit"))
    payload = celery.tasks[INBOX_DRAIN_TASK].function(task)
    assert payload == {
        "capability": "inbox_sync",
        "state": "idle",
        "worker_id": "celery:delivery-unit",
        "job_id": None,
        "claimed_jobs": 0,
        "completed_jobs": 0,
        "failed_jobs": 0,
        "processed_items": 0,
        "duplicate_items": 0,
    }

    reprocessed = cast(
        dict[str, str | int | None],
        celery.tasks[INBOX_REPROCESS_TASK].function(
            task,
            "ORG-0001",
            "ISJ-UNIT",
        ),
    )
    assert reprocessed["state"] == "requeued"
    assert reprocessed["job_id"] == "ISJ-UNIT"


def test_celery_delivery_relies_on_postgres_for_worker_loss_recovery() -> None:
    runner = _Runner()
    celery = create_celery_app(
        app_settings=Settings(),
        job_settings=AsyncJobSettings(
            broker_url="redis://127.0.0.1:6379/0",
            result_backend_url="redis://127.0.0.1:6379/1",
        ),
        runner_factory=cast(Callable[[], AsyncJobRunner], lambda: runner),
    )

    assert celery.conf.task_acks_late is True
    assert celery.conf.task_reject_on_worker_lost is False
    assert celery.conf.worker_prefetch_multiplier == 1
    assert AsyncJobSettings().lease_duration_seconds() > celery.conf.task_time_limit
