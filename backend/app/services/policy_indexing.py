from datetime import UTC, datetime

from app.domain.policy_indexing import PolicyIndexDrainResult
from app.domain.retrieval_v2 import PolicyIndexJobRecord
from app.ports.policy_indexing import PolicyIndexUnitOfWorkFactory
from app.retrieval.embeddings import EmbeddingProvider

POLICY_INDEX_MAX_ATTEMPTS = 3


class PolicyIndexingService:
    def __init__(
        self,
        *,
        unit_of_work: PolicyIndexUnitOfWorkFactory,
        embedding_provider: EmbeddingProvider,
        profile_key: str,
        job_limit: int,
        page_budget: int,
        lease_seconds: int = 90,
    ) -> None:
        if embedding_provider.version != profile_key:
            raise ValueError("The policy index profile and embedding provider do not match.")
        if embedding_provider.dimensions != 512:
            raise ValueError("The policy index requires 512-dimensional embeddings.")
        self._unit_of_work = unit_of_work
        self._embedding_provider = embedding_provider
        self._profile_key = profile_key
        self._job_limit = job_limit
        self._page_budget = page_budget
        self._lease_seconds = lease_seconds

    def enqueue(self) -> int:
        with self._unit_of_work() as uow:
            return uow.jobs.enqueue_missing(
                profile_key=self._profile_key,
                job_limit=self._job_limit,
                page_budget=self._page_budget,
            )

    def job_status(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> PolicyIndexJobRecord | None:
        with self._unit_of_work() as uow:
            return uow.jobs.get_by_public_id(
                organization_public_id=organization_public_id,
                job_public_id=job_public_id,
            )

    def reprocess(
        self,
        *,
        organization_public_id: str,
        job_public_id: str,
    ) -> PolicyIndexJobRecord:
        """Requeue a dead job while preserving already indexed clauses."""
        with self._unit_of_work() as uow:
            return uow.jobs.reprocess(
                organization_public_id=organization_public_id,
                job_public_id=job_public_id,
            )

    def drain(self, *, worker_id: str) -> PolicyIndexDrainResult:
        self.enqueue()
        claimed = completed = failed = indexed = skipped = 0
        for _ in range(self._job_limit):
            now = datetime.now(UTC)
            with self._unit_of_work() as uow:
                work = uow.jobs.claim(
                    profile_key=self._profile_key,
                    worker_id=worker_id,
                    now=now,
                    lease_seconds=self._lease_seconds,
                    max_attempts=POLICY_INDEX_MAX_ATTEMPTS,
                )
            if work is None:
                break
            claimed += 1
            try:
                vectors = tuple(
                    self._embedding_provider.embed(clause.text) for clause in work.clauses
                )
                with self._unit_of_work() as uow:
                    job = uow.jobs.persist_page(
                        work=work,
                        vectors=vectors,
                        now=datetime.now(UTC),
                    )
                indexed += job.indexed_clause_count - work.job.indexed_clause_count
                skipped += job.skipped_clause_count - work.job.skipped_clause_count
                completed += int(job.status.value == "completed")
            except Exception as exc:
                failed += 1
                with self._unit_of_work() as uow:
                    uow.jobs.fail(
                        work=work,
                        error_code=type(exc).__name__,
                        now=datetime.now(UTC),
                        max_attempts=POLICY_INDEX_MAX_ATTEMPTS,
                    )
        return PolicyIndexDrainResult(
            claimed_jobs=claimed,
            completed_jobs=completed,
            failed_jobs=failed,
            indexed_clauses=indexed,
            skipped_clauses=skipped,
        )
