from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from math import sqrt
from time import perf_counter
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.policies import (
    GovernedPolicyClauseRecord,
    GovernedPolicyVersionRecord,
    PolicyCandidateRecord,
    PolicyLifecycleStatus,
    PolicyRecord,
    PolicySourceKind,
    PolicyVersionStatus,
)
from app.domain.retrieval_v2 import HybridPolicyCandidatePage
from app.evaluation.retrieval_v2_workspace import (
    benchmark_actor,
    benchmark_as_of,
    benchmark_workspace,
)
from app.evaluation.wave1_rag_contract import (
    Wave1RagFixture,
    Wave1RagSourceFixture,
)
from app.evaluation.wave1_rag_observability import RagEventSink, make_rag_event
from app.evaluation.wave1_rag_scoring import (
    Wave1RagCaseObservation,
    Wave1RagReport,
    score_wave1_rag,
)
from app.retrieval.v2.embeddings import (
    DETERMINISTIC_POLICY_PROFILE,
    deterministic_policy_embedding_provider,
)
from app.retrieval.v2.retriever import V2PolicyRetrieval
from app.retrieval.v2.rrf import RRF_ALGORITHM_VERSION

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {"a", "an", "and", "are", "be", "before", "for", "is", "of", "or", "the", "to"}
)


class InMemoryHybridPolicyStore:
    """Credential-free adapter for exercising the real governed V2 resolver."""

    def __init__(self, fixture: Wave1RagFixture) -> None:
        self._fixture = fixture
        self._provider = deterministic_policy_embedding_provider()

    def inspect_hybrid_scope(self, **values: object) -> HybridPolicyCandidatePage:
        organization_public_id = str(values["organization_public_id"])
        profile_key = str(values["profile_key"])
        if organization_public_id.endswith("-MISSING"):
            return _scope(profile_key=profile_key, category_matches=0)
        if organization_public_id.endswith("-INDEXING"):
            return _scope(profile_key=profile_key, index_ready=False)
        matching = self._matching_sources(values)
        return _scope(
            profile_key=profile_key,
            category_matches=len(matching),
            applicable_matches=len(matching),
            active_matches=len(matching),
        )

    def search_hybrid_candidates(self, **values: object) -> HybridPolicyCandidatePage:
        query_text = str(values["query_text"])
        raw_query_embedding = values["query_embedding"]
        raw_candidate_limit = values["candidate_limit"]
        if not isinstance(raw_query_embedding, list):
            raise TypeError("query_embedding must be a list")
        if not isinstance(raw_candidate_limit, int):
            raise TypeError("candidate_limit must be an integer")
        query_embedding = [float(item) for item in raw_query_embedding]
        candidate_limit = raw_candidate_limit
        profile_key = str(values["profile_key"])
        sources = self._matching_sources(values)
        candidates = [
            _candidate(source=source, clause_index=index)
            for source in sources
            for index in range(len(source.clauses))
        ]
        dense = sorted(
            candidates,
            key=lambda candidate: (
                -_cosine(
                    query_embedding,
                    self._provider.embed(_candidate_text(candidate)),
                ),
                candidate.clauses[0].public_id,
            ),
        )[:candidate_limit]
        query_tokens = _tokens(query_text)
        lexical = sorted(
            candidates,
            key=lambda candidate: (
                -len(query_tokens & _tokens(_candidate_text(candidate))),
                candidate.clauses[0].public_id,
            ),
        )[:candidate_limit]
        count = len(sources)
        return HybridPolicyCandidatePage(
            profile_key=profile_key,
            index_ready=True,
            category_matches=count,
            applicable_matches=count,
            active_matches=count,
            dense=tuple(dense),
            lexical=tuple(lexical),
        )

    def _matching_sources(self, values: dict[str, object]) -> tuple[Wave1RagSourceFixture, ...]:
        category = str(values["case_category"])
        raw_products = values["products"]
        if not isinstance(raw_products, set):
            raise TypeError("products must be a set")
        products = {str(item) for item in raw_products}
        region = str(values["region"])
        channel = str(values["channel"])
        tier = str(values["customer_tier"])
        as_of = values["as_of"]
        if not isinstance(as_of, datetime):
            raise TypeError("as_of must be a datetime")
        return tuple(
            source
            for source in self._fixture.sources
            if _matches(category, source.case_categories)
            and _matches_any(products, source.products)
            and _matches(region, source.regions)
            and _matches(channel, source.channels)
            and _matches(tier, source.customer_tiers)
            and _active(source, as_of)
        )


def run_wave1_rag_evaluation(
    *,
    fixture: Wave1RagFixture,
    event_sink: RagEventSink | None = None,
    run_id: str = "wave1-rag-local",
    timer: Callable[[], float] = perf_counter,
) -> Wave1RagReport:
    provider = deterministic_policy_embedding_provider()
    store = InMemoryHybridPolicyStore(fixture)
    resolver = V2PolicyRetrieval(
        store=store,
        embedding_provider=provider,
        profile_key=provider.version,
        query_character_limit=2000,
    )
    observations: list[Wave1RagCaseObservation] = []
    for case in fixture.cases:
        started = timer()
        observed_status = None
        retrieved_source_ids: tuple[str, ...] = ()
        error_code = None
        try:
            resolution = resolver.resolve(
                actor=benchmark_actor(case.organization_public_id),
                workspace=benchmark_workspace(case),
                as_of=benchmark_as_of(case),
                correlation_id=f"{run_id}:{case.id.lower()}",
            )
            observed_status = resolution.status
            retrieved_source_ids = tuple(
                binding.clause.public_id for binding in resolution.bindings
            )
        except Exception as exc:  # The report must retain case-level failure visibility.
            error_code = type(exc).__name__
        latency_ms = round((timer() - started) * 1000, 3)
        observation = Wave1RagCaseObservation(
            case_id=case.id,
            expected_status=case.expected_status,
            observed_status=observed_status,
            expected_source_ids=case.expected_source_ids,
            retrieved_source_ids=retrieved_source_ids,
            latency_ms=latency_ms,
            error_code=error_code,
        )
        observations.append(observation)
        if event_sink is not None:
            event_sink.emit(
                make_rag_event(
                    run_id=run_id,
                    case_id=case.id,
                    expected_status=case.expected_status,
                    observed_status=observed_status,
                    retrieved_source_ids=retrieved_source_ids,
                    latency_ms=latency_ms,
                    error_code=error_code,
                )
            )
    return score_wave1_rag(fixture=fixture, observations=tuple(observations))


def _candidate(*, source: Wave1RagSourceFixture, clause_index: int) -> PolicyCandidateRecord:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    organization_id = _stable_uuid("ORG-WAVE1")
    policy_id = _stable_uuid(source.public_id)
    version_id = _stable_uuid(f"{source.public_id}:v1")
    clause_fixture = source.clauses[clause_index]
    clause_text = clause_fixture.text
    source_text = "\n\n".join(f"## {clause.heading}\n{clause.text}" for clause in source.clauses)
    policy = PolicyRecord(
        id=policy_id,
        public_id=source.public_id,
        organization_id=organization_id,
        title=source.title,
        description="Synthetic credential-free Wave 1 RAG evaluation source.",
        status=PolicyLifecycleStatus.PUBLISHED,
        owner_id=_stable_uuid(f"{source.public_id}:owner"),
        source_kind=PolicySourceKind.MANUAL,
        source_name="Wave 1 synthetic evaluation fixture",
        source_error=None,
        current_version=1,
        version=1,
        created_at=now,
        updated_at=now,
    )
    version = GovernedPolicyVersionRecord(
        id=version_id,
        public_id=f"POLV-{sha256(source.public_id.encode()).hexdigest()[:12].upper()}",
        organization_id=organization_id,
        policy_id=policy_id,
        legacy_policy_version_id=None,
        version=1,
        record_version=1,
        status=PolicyVersionStatus.PUBLISHED,
        immutable=True,
        source_text=source_text,
        content_hash=sha256(source_text.encode()).hexdigest(),
        decision_scope=source.decision_scope,
        case_categories=list(source.case_categories),
        products=list(source.products),
        regions=list(source.regions),
        channels=list(source.channels),
        customer_tiers=list(source.customer_tiers),
        effective_from=_timestamp(source.effective_from),
        effective_to=_timestamp(source.effective_to) if source.effective_to else None,
        created_by="USR-WAVE1-EVAL",
        created_at=now,
        submitted_at=now,
        published_at=now,
        retired_at=None,
    )
    provider = deterministic_policy_embedding_provider()
    clause = GovernedPolicyClauseRecord(
        id=_stable_uuid(clause_fixture.public_id),
        public_id=clause_fixture.public_id,
        organization_id=organization_id,
        policy_id=policy_id,
        policy_version_id=version_id,
        sequence=clause_index + 1,
        heading=clause_fixture.heading,
        text=clause_text,
        applies_when=f"Scope {source.decision_scope}.",
        content_hash=sha256(clause_text.encode()).hexdigest(),
        chunking_version="wave1-synthetic-clause-v1",
        embedding_version=DETERMINISTIC_POLICY_PROFILE,
        index_version=RRF_ALGORITHM_VERSION,
        embedding=provider.embed(clause_text),
    )
    return PolicyCandidateRecord(policy=policy, version=version, clauses=[clause])


def _scope(
    *,
    profile_key: str,
    index_ready: bool = True,
    category_matches: int = 1,
    applicable_matches: int | None = None,
    active_matches: int | None = None,
) -> HybridPolicyCandidatePage:
    applicable = category_matches if applicable_matches is None else applicable_matches
    active = applicable if active_matches is None else active_matches
    return HybridPolicyCandidatePage(
        profile_key=profile_key,
        index_ready=index_ready,
        category_matches=category_matches,
        applicable_matches=applicable,
        active_matches=active,
    )


def _matches(value: str, allowed: tuple[str, ...]) -> bool:
    return "all" in allowed or value in allowed


def _matches_any(values: set[str], allowed: tuple[str, ...]) -> bool:
    return "all" in allowed or bool(values & set(allowed))


def _active(source: Wave1RagSourceFixture, as_of: datetime) -> bool:
    start = _timestamp(source.effective_from)
    end = _timestamp(source.effective_to) if source.effective_to else None
    return start <= as_of and (end is None or as_of < end)


def _timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _tokens(value: str) -> set[str]:
    return {token for token in _TOKEN.findall(value.lower()) if token not in _STOP_WORDS}


def _candidate_text(candidate: PolicyCandidateRecord) -> str:
    clause = candidate.clauses[0]
    return f"{candidate.policy.title} {clause.heading} {clause.text}"


def _cosine(left: list[float], right: list[float]) -> float:
    denominator = sqrt(sum(value * value for value in left)) * sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator


def _stable_uuid(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"case-resolution-copilot:wave1-rag:{value}")
