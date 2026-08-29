from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.policy_indexing import PolicyIndexWorkItem
from app.domain.retrieval_v2 import PolicyIndexJobRecord

from .job_queue import claim, enqueue_missing, get_by_public_id, reprocess
from .job_results import fail, persist_page


class PolicyIndexRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue_missing(
        self,
        *,
        profile_key: str,
        job_limit: int,
        page_budget: int,
    ) -> int:
        return enqueue_missing(
            self._session,
            profile_key=profile_key,
            job_limit=job_limit,
            page_budget=page_budget,
        )

    def claim(
        self,
        *,
        profile_key: str,
        worker_id: str,
        now: datetime,
        lease_seconds: int,
        max_attempts: int,
    ) -> PolicyIndexWorkItem | None:
        return claim(
            self._session,
            profile_key=profile_key,
            worker_id=worker_id,
            now=now,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
        )

    def get_by_public_id(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> PolicyIndexJobRecord | None:
        return get_by_public_id(
            self._session,
            organization_public_id=organization_public_id,
            job_public_id=job_public_id,
        )

    def reprocess(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> PolicyIndexJobRecord:
        return reprocess(
            self._session,
            organization_public_id=organization_public_id,
            job_public_id=job_public_id,
        )

    def persist_page(
        self,
        *,
        work: PolicyIndexWorkItem,
        vectors: tuple[list[float], ...],
        now: datetime,
    ) -> PolicyIndexJobRecord:
        return persist_page(self._session, work=work, vectors=vectors, now=now)

    def fail(
        self,
        *,
        work: PolicyIndexWorkItem,
        error_code: str,
        now: datetime,
        max_attempts: int,
    ) -> PolicyIndexJobRecord:
        return fail(
            self._session,
            work=work,
            error_code=error_code,
            now=now,
            max_attempts=max_attempts,
        )
