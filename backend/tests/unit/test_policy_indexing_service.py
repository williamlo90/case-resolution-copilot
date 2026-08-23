from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import uuid4

from app.domain.policy_indexing import PolicyIndexClauseRecord, PolicyIndexWorkItem
from app.domain.retrieval_v2 import (
    EmbeddingProfileRecord,
    EmbeddingProfileStatus,
    PolicyIndexJobRecord,
    PolicyIndexJobStatus,
)
from app.persistence.models import GovernedPolicyClauseModel
from app.retrieval.v2.embeddings import DETERMINISTIC_POLICY_PROFILE
from app.services.policy_indexing import PolicyIndexingService

NOW = datetime(2026, 8, 14, 8, 0, tzinfo=UTC)


def test_policy_index_clause_record_accepts_an_orm_row() -> None:
    row = GovernedPolicyClauseModel(
        id=uuid4(),
        public_id="POLC-UNIT-0001",
        organization_id=uuid4(),
        policy_id=uuid4(),
        policy_version_id=uuid4(),
        sequence=1,
        heading="Duplicate charge",
        text="A verified duplicate charge requires invoice review.",
        applies_when="The customer disputes a billing transaction.",
        content_hash="d" * 64,
        chunking_version="governed-heading-v1",
        embedding_version="deterministic-hash-v1-d32",
        index_version="policy-hybrid-v1",
        embedding=[0.0] * 32,
    )

    record = PolicyIndexClauseRecord.model_validate(row)

    assert record.id == row.id
    assert record.text == row.text


def _work() -> PolicyIndexWorkItem:
    organization_id = uuid4()
    policy_id = uuid4()
    version_id = uuid4()
    profile = EmbeddingProfileRecord(
        id=uuid4(),
        profile_key=DETERMINISTIC_POLICY_PROFILE,
        environment="development",
        provider="deterministic",
        model="sha256-token-sign-v2",
        dimensions=512,
        normalization_version="policy-normalization-v2",
        chunking_version="governed-heading-v1",
        index_version="policy-hybrid-rrf-v2",
        status=EmbeddingProfileStatus.BUILDING,
        expected_clause_count=1,
        indexed_clause_count=0,
        build_fingerprint="a" * 64,
        created_at=NOW,
        ready_at=None,
        activated_by=None,
        retired_at=None,
    )
    job = PolicyIndexJobRecord(
        id=uuid4(),
        public_id="PIJ-UNIT-0001",
        organization_id=organization_id,
        profile_id=profile.id,
        policy_id=policy_id,
        policy_version_id=version_id,
        source_content_fingerprint="b" * 64,
        job_key="c" * 64,
        status=PolicyIndexJobStatus.RUNNING,
        page_budget=1,
        attempt_count=1,
        available_at=NOW,
        lease_owner="worker-unit",
        lease_expires_at=NOW + timedelta(seconds=90),
        last_error_code=None,
        indexed_clause_count=0,
        skipped_clause_count=0,
        completed_at=None,
        created_at=NOW,
    )
    clause = PolicyIndexClauseRecord(
        id=uuid4(),
        organization_id=organization_id,
        policy_id=policy_id,
        policy_version_id=version_id,
        sequence=1,
        text="A verified duplicate charge requires invoice review.",
        content_hash="d" * 64,
    )
    return PolicyIndexWorkItem(
        job=job,
        profile=profile,
        clauses=(clause,),
        lease_expires_at=job.lease_expires_at,
    )


class _Store:
    def __init__(self, work: PolicyIndexWorkItem) -> None:
        self.work = work
        self.claimed = False
        self.persisted_vectors: tuple[list[float], ...] | None = None
        self.failed = False

    def enqueue_missing(self, **values: object) -> int:
        del values
        return 1

    def claim(self, **values: object) -> PolicyIndexWorkItem | None:
        del values
        if self.claimed:
            return None
        self.claimed = True
        return self.work

    def persist_page(
        self,
        *,
        work: PolicyIndexWorkItem,
        vectors: tuple[list[float], ...],
        now: datetime,
    ) -> PolicyIndexJobRecord:
        del now
        self.persisted_vectors = vectors
        return work.job.model_copy(
            update={
                "status": PolicyIndexJobStatus.COMPLETED,
                "indexed_clause_count": 1,
                "completed_at": NOW,
            }
        )

    def fail(self, **values: object) -> PolicyIndexJobRecord:
        del values
        self.failed = True
        return self.work.job.model_copy(update={"status": PolicyIndexJobStatus.FAILED})


class _UnitOfWork:
    def __init__(self, factory: "_Factory") -> None:
        self._factory = factory
        self.jobs = factory.store

    def __enter__(self) -> "_UnitOfWork":
        self._factory.active += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self._factory.active -= 1


class _Factory:
    def __init__(self, store: _Store) -> None:
        self.store = store
        self.active = 0

    def __call__(self) -> _UnitOfWork:
        return _UnitOfWork(self)


class _ObservedProvider:
    version = DETERMINISTIC_POLICY_PROFILE
    dimensions = 512

    def __init__(self, factory: _Factory) -> None:
        self._factory = factory
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        assert text
        assert self._factory.active == 0
        self.calls += 1
        return [0.125] * self.dimensions


def test_index_provider_runs_outside_the_database_unit_of_work() -> None:
    store = _Store(_work())
    factory = _Factory(store)
    provider = _ObservedProvider(factory)
    service = PolicyIndexingService(
        unit_of_work=factory,
        embedding_provider=provider,
        profile_key=DETERMINISTIC_POLICY_PROFILE,
        job_limit=2,
        page_budget=1,
    )

    result = service.drain(worker_id="worker-unit")

    assert result.claimed_jobs == 1
    assert result.completed_jobs == 1
    assert result.indexed_clauses == 1
    assert provider.calls == 1
    assert store.persisted_vectors is not None
    assert not store.failed
    assert factory.active == 0
