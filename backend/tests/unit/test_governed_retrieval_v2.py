from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.policies import (
    EvidenceRetrievalStatus,
    GovernedPolicyClauseRecord,
    GovernedPolicyVersionRecord,
    PolicyCandidateRecord,
    PolicyLifecycleStatus,
    PolicyRecord,
    PolicySourceKind,
    PolicyVersionStatus,
)
from app.domain.retrieval_v2 import HybridPolicyCandidatePage
from app.persistence.policies.retrieval_v2 import (
    DENSE_MAX_COSINE_DISTANCE,
    LEXICAL_MIN_RANK,
)
from app.persistence.policies.retrieval_v2_query import (
    LEXICAL_QUERY_TERM_LIMIT,
    lexical_websearch_query,
)
from app.retrieval.governed_facade import (
    GovernedPolicyRetrievalFacade,
    RetrievalResolution,
)
from app.retrieval.v2.embeddings import (
    DETERMINISTIC_POLICY_PROFILE,
    POLICY_V2_DIMENSIONS,
    deterministic_policy_embedding_provider,
)
from app.retrieval.v2.query import build_policy_query
from app.retrieval.v2.retriever import V2PolicyRetrieval
from app.retrieval.v2.rrf import RRF_ALGORITHM_VERSION, fuse_rankings, select_diverse
from app.security.authentication import DeterministicAuthProvider
from tests.builders import valid_case_workspace

NOW = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)


def _candidate(
    public_id: str,
    *,
    sequence: int = 1,
    policy_id: UUID | None = None,
) -> PolicyCandidateRecord:
    organization_id = uuid4()
    resolved_policy_id = policy_id or uuid4()
    version_id = uuid4()
    policy = PolicyRecord(
        id=resolved_policy_id,
        public_id=public_id,
        organization_id=organization_id,
        title=f"Policy {public_id}",
        description="A governed retrieval test policy.",
        status=PolicyLifecycleStatus.PUBLISHED,
        owner_id=uuid4(),
        source_kind=PolicySourceKind.MANUAL,
        source_name="Unit test",
        source_error=None,
        current_version=1,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    version = GovernedPolicyVersionRecord(
        id=version_id,
        public_id=f"POLV-{uuid4().hex[:12].upper()}",
        organization_id=organization_id,
        policy_id=resolved_policy_id,
        legacy_policy_version_id=None,
        version=1,
        record_version=1,
        status=PolicyVersionStatus.PUBLISHED,
        immutable=True,
        source_text="Verified duplicate charges require invoice review.",
        content_hash="a" * 64,
        decision_scope="billing_adjustment",
        case_categories=["billing_dispute"],
        products=["all"],
        regions=["all"],
        channels=["all"],
        customer_tiers=["all"],
        effective_from=NOW,
        effective_to=None,
        created_by="USR-0003",
        created_at=NOW,
        submitted_at=NOW,
        published_at=NOW,
        retired_at=None,
    )
    clause = GovernedPolicyClauseRecord(
        id=uuid4(),
        public_id=f"POLC-{uuid4().hex[:12].upper()}",
        organization_id=organization_id,
        policy_id=resolved_policy_id,
        policy_version_id=version_id,
        sequence=sequence,
        heading=f"Clause {sequence}",
        text="Review the invoice before correcting a verified duplicate charge.",
        applies_when="The customer disputes a billing transaction.",
        content_hash="b" * 64,
        chunking_version="governed-heading-v1",
        embedding_version=DETERMINISTIC_POLICY_PROFILE,
        index_version=RRF_ALGORITHM_VERSION,
        embedding=[0.0] * POLICY_V2_DIMENSIONS,
    )
    return PolicyCandidateRecord(policy=policy, version=version, clauses=[clause])


def test_deterministic_v2_embedding_is_stable_normalized_and_512_dimensions() -> None:
    provider = deterministic_policy_embedding_provider()

    first = provider.embed("A duplicate invoice charge needs review.")
    second = provider.embed("A duplicate invoice charge needs review.")

    assert first == second
    assert len(first) == POLICY_V2_DIMENSIONS
    assert sum(value * value for value in first) == pytest.approx(1.0)
    assert provider.version == DETERMINISTIC_POLICY_PROFILE


def test_v2_candidate_sources_have_explicit_relevance_floors() -> None:
    assert 0 < DENSE_MAX_COSINE_DISTANCE < 1
    assert LEXICAL_MIN_RANK > 0


def test_v2_lexical_query_is_bounded_deterministic_and_uses_or_terms() -> None:
    text = (
        "The customer reports the same invoice charge twice and asks support "
        "to confirm the payment before correcting duplicate billing."
    )

    query = lexical_websearch_query(text)

    assert query == lexical_websearch_query(text)
    assert "invoice OR charge" in query
    assert "duplicate OR billing" in query
    assert "customer" not in query
    assert len(query.split(" OR ")) <= LEXICAL_QUERY_TERM_LIMIT


def test_policy_query_removes_direct_identifiers_and_respects_its_budget() -> None:
    query = build_policy_query(
        category="billing dispute",
        issue="Contact jane@example.com or +62 812-3456-7890 about the invoice.",
        request_summary="Card 4111 1111 1111 1111 appears to have been charged twice.",
        products={"billing core"},
        requested_remedy="Refund jane@example.com after checking +62 812-3456-7890.",
        max_characters=240,
    )

    assert len(query.text) <= 240
    assert "jane@example.com" not in query.text
    assert "812-3456-7890" not in query.text
    assert "4111 1111 1111 1111" not in query.text
    assert query.fingerprint == build_policy_query(
        category="billing dispute",
        issue="Contact jane@example.com or +62 812-3456-7890 about the invoice.",
        request_summary="Card 4111 1111 1111 1111 appears to have been charged twice.",
        products={"billing core"},
        requested_remedy="Refund jane@example.com after checking +62 812-3456-7890.",
        max_characters=240,
    ).fingerprint


def test_rrf_is_deterministic_and_keeps_both_source_ranks() -> None:
    policy_a = _candidate("POL-A")
    policy_b = _candidate("POL-B")

    ranked = fuse_rankings(dense=[policy_a, policy_b], lexical=[policy_b, policy_a])

    assert [item.candidate.policy.public_id for item in ranked] == ["POL-A", "POL-B"]
    assert (ranked[0].dense_rank, ranked[0].lexical_rank) == (1, 2)
    assert (ranked[1].dense_rank, ranked[1].lexical_rank) == (2, 1)
    assert ranked[0].fused_score == pytest.approx(ranked[1].fused_score)


def test_diversity_limits_one_policy_when_another_authority_is_available() -> None:
    shared_policy_id = uuid4()
    policy_a = [
        _candidate("POL-A", sequence=sequence, policy_id=shared_policy_id)
        for sequence in range(1, 4)
    ]
    policy_b = _candidate("POL-B")

    selected = select_diverse(
        fuse_rankings(
            dense=[*policy_a, policy_b],
            lexical=[*policy_a, policy_b],
        )
    )

    assert [item.candidate.policy.public_id for item in selected] == [
        "POL-A",
        "POL-A",
        "POL-B",
    ]


class _HybridStore:
    def __init__(self, candidate: PolicyCandidateRecord) -> None:
        self.candidate = candidate
        self.search_calls = 0

    def inspect_hybrid_scope(self, **values: object) -> HybridPolicyCandidatePage:
        del values
        return HybridPolicyCandidatePage(
            profile_key=DETERMINISTIC_POLICY_PROFILE,
            index_ready=True,
            category_matches=1,
            applicable_matches=1,
            active_matches=1,
        )

    def search_hybrid_candidates(self, **values: object) -> HybridPolicyCandidatePage:
        del values
        self.search_calls += 1
        return HybridPolicyCandidatePage(
            profile_key=DETERMINISTIC_POLICY_PROFILE,
            index_ready=True,
            category_matches=1,
            applicable_matches=1,
            active_matches=1,
            dense=(self.candidate,),
            lexical=(self.candidate,),
        )


class _ObservedEmbeddingProvider:
    version = DETERMINISTIC_POLICY_PROFILE
    dimensions = POLICY_V2_DIMENSIONS

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return [0.0] * self.dimensions


class _IncompleteIndexStore(_HybridStore):
    def inspect_hybrid_scope(self, **values: object) -> HybridPolicyCandidatePage:
        del values
        return HybridPolicyCandidatePage(
            profile_key=DETERMINISTIC_POLICY_PROFILE,
            index_ready=False,
            category_matches=1,
            applicable_matches=1,
            active_matches=1,
        )


def test_v2_retrieval_checks_index_readiness_before_embedding_the_query() -> None:
    store = _IncompleteIndexStore(_candidate("POL-BILLING"))
    provider = _ObservedEmbeddingProvider()
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = V2PolicyRetrieval(
        store=store,
        embedding_provider=provider,
        profile_key=DETERMINISTIC_POLICY_PROFILE,
        query_character_limit=1000,
    ).resolve(
        actor=actor,
        workspace=valid_case_workspace(),
        as_of=NOW,
        correlation_id="corr-index-not-ready",
    )

    assert result.status is EvidenceRetrievalStatus.MISSING
    assert provider.calls == 0
    assert store.search_calls == 0


def test_v2_retrieval_records_versioned_rank_and_query_metadata() -> None:
    store = _HybridStore(_candidate("POL-BILLING"))
    actor = DeterministicAuthProvider().authenticate("USR-0001")
    result = V2PolicyRetrieval(
        store=store,
        embedding_provider=deterministic_policy_embedding_provider(),
        profile_key=DETERMINISTIC_POLICY_PROFILE,
        query_character_limit=1000,
    ).resolve(
        actor=actor,
        workspace=valid_case_workspace(),
        as_of=NOW,
        correlation_id="corr-v2-test",
    )

    assert result.status is EvidenceRetrievalStatus.RELEVANT
    assert store.search_calls == 1
    assert len(result.bindings) == 1
    binding = result.bindings[0]
    assert binding.embedding_profile_key == DETERMINISTIC_POLICY_PROFILE
    assert binding.retrieval_algorithm_version == RRF_ALGORITHM_VERSION
    assert binding.query_fingerprint is not None
    assert binding.dense_rank == 1
    assert binding.lexical_rank == 1
    assert binding.retrieval_run_correlation_id == "corr-v2-test"


class _FixedRetriever:
    def __init__(self, reason: str) -> None:
        self.result = RetrievalResolution(EvidenceRetrievalStatus.MISSING, reason, [])
        self.calls = 0

    def resolve(self, **values: object) -> RetrievalResolution:
        del values
        self.calls += 1
        return self.result


class _FailingRetriever:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, **values: object) -> RetrievalResolution:
        del values
        self.calls += 1
        raise RuntimeError("shadow unavailable")


def test_shadow_mode_observes_v2_but_preserves_the_v1_result() -> None:
    v1 = _FixedRetriever("v1 result")
    v2 = _FixedRetriever("v2 shadow result")
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = GovernedPolicyRetrievalFacade(v1=v1, v2=v2, mode="v2_shadow").resolve(
        actor=actor,
        workspace=valid_case_workspace(),
        as_of=NOW,
        correlation_id="corr-shadow-test",
    )

    assert result.reason == "v1 result"
    assert v1.calls == 1
    assert v2.calls == 1


def test_shadow_mode_isolates_v2_failures_from_the_v1_result() -> None:
    v1 = _FixedRetriever("v1 result")
    v2 = _FailingRetriever()
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = GovernedPolicyRetrievalFacade(v1=v1, v2=v2, mode="v2_shadow").resolve(
        actor=actor,
        workspace=valid_case_workspace(),
        as_of=NOW,
        correlation_id="corr-shadow-failure",
    )

    assert result.reason == "v1 result"
    assert v1.calls == 1
    assert v2.calls == 1
