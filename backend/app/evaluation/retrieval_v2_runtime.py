from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Literal

from app.domain.policies import (
    EvidenceRetrievalStatus,
    PolicyNotFound,
    PolicyRetrievalCandidatePage,
)
from app.domain.retrieval_v2 import HybridPolicyCandidatePage
from app.evaluation.retrieval_v2_contract import (
    GuardScopeFixture,
    RetrievalBenchmarkInputSuite,
)
from app.evaluation.retrieval_v2_scoring import (
    RetrievalCaseObservation,
    RetrievedClauseObservation,
)
from app.evaluation.retrieval_v2_workspace import (
    benchmark_actor,
    benchmark_as_of,
    benchmark_workspace,
)
from app.persistence.database import Database
from app.persistence.policy_repository import PolicyRepository
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.governed_facade import RetrievalResolution
from app.retrieval.v1_governed import V1PolicyRetrieval
from app.retrieval.v2.retriever import V2PolicyRetrieval

RetrievalGeneration = Literal["v1", "v2"]


class MeasuredEmbeddingProvider:
    def __init__(self, delegate: EmbeddingProvider) -> None:
        self._delegate = delegate
        self.calls = 0

    @property
    def version(self) -> str:
        return self._delegate.version

    @property
    def dimensions(self) -> int:
        return self._delegate.dimensions

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return self._delegate.embed(text)


class TransactionScopedPolicyStore:
    """Opens a short session for each store operation and never spans provider calls."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def search_retrieval_candidates(
        self,
        *,
        organization_public_id: str,
        case_category: str,
        products: set[str],
        region: str,
        channel: str,
        customer_tier: str,
        as_of: datetime,
        query_embedding: list[float],
        embedding_version: str,
        candidate_limit: int,
    ) -> PolicyRetrievalCandidatePage:
        with self._database.session() as session:
            return PolicyRepository(session).search_retrieval_candidates(
                organization_public_id=organization_public_id,
                case_category=case_category,
                products=products,
                region=region,
                channel=channel,
                customer_tier=customer_tier,
                as_of=as_of,
                query_embedding=query_embedding,
                embedding_version=embedding_version,
                candidate_limit=candidate_limit,
            )

    def inspect_hybrid_scope(
        self,
        *,
        organization_public_id: str,
        profile_key: str,
        case_category: str,
        products: set[str],
        region: str,
        channel: str,
        customer_tier: str,
        as_of: datetime,
    ) -> HybridPolicyCandidatePage:
        with self._database.session() as session:
            return PolicyRepository(session).inspect_hybrid_scope(
                organization_public_id=organization_public_id,
                profile_key=profile_key,
                case_category=case_category,
                products=products,
                region=region,
                channel=channel,
                customer_tier=customer_tier,
                as_of=as_of,
            )

    def search_hybrid_candidates(
        self,
        *,
        organization_public_id: str,
        profile_key: str,
        case_category: str,
        products: set[str],
        region: str,
        channel: str,
        customer_tier: str,
        as_of: datetime,
        query_text: str,
        query_embedding: list[float],
        candidate_limit: int,
    ) -> HybridPolicyCandidatePage:
        with self._database.session() as session:
            return PolicyRepository(session).search_hybrid_candidates(
                organization_public_id=organization_public_id,
                profile_key=profile_key,
                case_category=case_category,
                products=products,
                region=region,
                channel=channel,
                customer_tier=customer_tier,
                as_of=as_of,
                query_text=query_text,
                query_embedding=query_embedding,
                candidate_limit=candidate_limit,
            )


class FrozenGuardStore:
    def __init__(self, fixture: GuardScopeFixture) -> None:
        self._fixture = fixture

    def search_retrieval_candidates(self, **values: object) -> PolicyRetrievalCandidatePage:
        del values
        fixture = self._fixture
        return PolicyRetrievalCandidatePage(
            category_matches=fixture.category_matches,
            applicable_matches=fixture.applicable_matches,
            active_matches=fixture.active_matches,
            truncated=False,
            conflicting_scopes=list(fixture.conflicting_scopes),
            candidates=[],
        )

    def inspect_hybrid_scope(self, **values: object) -> HybridPolicyCandidatePage:
        profile_key = str(values["profile_key"])
        fixture = self._fixture
        return HybridPolicyCandidatePage(
            profile_key=profile_key,
            index_ready=fixture.index_ready,
            category_matches=fixture.category_matches,
            applicable_matches=fixture.applicable_matches,
            active_matches=fixture.active_matches,
            conflicting_scopes=fixture.conflicting_scopes,
        )

    def search_hybrid_candidates(self, **values: object) -> HybridPolicyCandidatePage:
        del values
        raise AssertionError("A frozen guard case must resolve before hybrid search.")


def run_retrieval_profile(
    *,
    database: Database,
    inputs: RetrievalBenchmarkInputSuite,
    embedding_provider: EmbeddingProvider,
    generation: RetrievalGeneration,
    query_character_limit: int = 2000,
) -> tuple[RetrievalCaseObservation, ...]:
    measured = MeasuredEmbeddingProvider(embedding_provider)
    database_store = TransactionScopedPolicyStore(database)
    observations: list[RetrievalCaseObservation] = []
    for case in inputs.cases:
        store: TransactionScopedPolicyStore | FrozenGuardStore = (
            database_store
            if case.guard_scope is None
            else FrozenGuardStore(case.guard_scope)
        )
        resolver = _resolver(
            generation=generation,
            store=store,
            embedding_provider=measured,
            query_character_limit=query_character_limit,
        )
        calls_before = measured.calls
        started = perf_counter()
        boundary_outcome: Literal["organization_not_found"] | None = None
        try:
            result = resolver.resolve(
                actor=benchmark_actor(case.organization_public_id),
                workspace=benchmark_workspace(case),
                as_of=benchmark_as_of(case),
                correlation_id=f"benchmark-{case.id.lower()}",
            )
        except PolicyNotFound:
            boundary_outcome = "organization_not_found"
            result = RetrievalResolution(
                status=EvidenceRetrievalStatus.MISSING,
                reason="The benchmark workspace has no accessible policy corpus.",
                bindings=[],
            )
        observations.append(
            RetrievalCaseObservation(
                case_id=case.id,
                status=result.status,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                embedding_calls=measured.calls - calls_before,
                boundary_outcome=boundary_outcome,
                clauses=tuple(
                    RetrievedClauseObservation(
                        policy_public_id=binding.policy.public_id,
                        policy_version=binding.version.version,
                        clause_public_id=binding.clause.public_id,
                        dense_rank=binding.dense_rank,
                        lexical_rank=binding.lexical_rank,
                        score=binding.retrieval_score,
                    )
                    for binding in result.bindings
                ),
            )
        )
    return tuple(observations)


def _resolver(
    *,
    generation: RetrievalGeneration,
    store: TransactionScopedPolicyStore | FrozenGuardStore,
    embedding_provider: EmbeddingProvider,
    query_character_limit: int,
) -> V1PolicyRetrieval | V2PolicyRetrieval:
    if generation == "v1":
        return V1PolicyRetrieval(store=store, embedding_provider=embedding_provider)
    return V2PolicyRetrieval(
        store=store,
        embedding_provider=embedding_provider,
        profile_key=embedding_provider.version,
        query_character_limit=query_character_limit,
    )
