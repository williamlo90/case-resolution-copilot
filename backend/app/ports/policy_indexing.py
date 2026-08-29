from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from app.domain.policy_indexing import PolicyIndexWorkItem
from app.domain.retrieval_v2 import PolicyIndexJobRecord


class PolicyIndexStore(Protocol):
    def enqueue_missing(
        self,
        *,
        profile_key: str,
        job_limit: int,
        page_budget: int,
    ) -> int: ...

    def claim(
        self,
        *,
        profile_key: str,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
        max_attempts: int,
    ) -> PolicyIndexWorkItem | None: ...

    def get_by_public_id(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> PolicyIndexJobRecord | None: ...

    def reprocess(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> PolicyIndexJobRecord: ...

    def persist_page(
        self,
        *,
        work: PolicyIndexWorkItem,
        vectors: tuple[list[float], ...],
        now: datetime,
    ) -> PolicyIndexJobRecord: ...

    def fail(
        self,
        *,
        work: PolicyIndexWorkItem,
        error_code: str,
        now: datetime,
        max_attempts: int,
    ) -> PolicyIndexJobRecord: ...


class PolicyIndexUnitOfWork(Protocol):
    jobs: PolicyIndexStore

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class PolicyIndexUnitOfWorkFactory(Protocol):
    def __call__(self) -> PolicyIndexUnitOfWork: ...
