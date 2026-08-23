from datetime import datetime
from hashlib import sha256
from typing import Protocol

from app.domain.cases import CaseWorkspaceRecord
from app.domain.identity import ActorContext
from app.domain.policies import (
    EvidenceRetrievalStatus,
    PolicyEvidenceBinding,
)
from app.domain.retrieval_v2 import HybridPolicyCandidatePage, RankedClause
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.governed_facade import RetrievalResolution
from app.retrieval.policy_context import (
    CaseRetrievalContext,
    case_context,
    context_label,
)
from app.retrieval.v2.query import build_policy_query
from app.retrieval.v2.rrf import RRF_ALGORITHM_VERSION, fuse_rankings, select_diverse

HYBRID_CANDIDATE_LIMIT = 32


class PolicyHybridRetrievalStore(Protocol):
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
    ) -> HybridPolicyCandidatePage: ...

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
    ) -> HybridPolicyCandidatePage: ...


class V2PolicyRetrieval:
    def __init__(
        self,
        *,
        store: PolicyHybridRetrievalStore,
        embedding_provider: EmbeddingProvider,
        profile_key: str,
        query_character_limit: int,
    ) -> None:
        if embedding_provider.dimensions != 512:
            raise ValueError("Policy RAG V2 requires 512-dimensional embeddings.")
        if embedding_provider.version != profile_key:
            raise ValueError("The configured embedding profile and provider do not match.")
        self._store = store
        self._embedding_provider = embedding_provider
        self._profile_key = profile_key
        self._query_character_limit = query_character_limit

    def resolve(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
        as_of: datetime,
        correlation_id: str,
    ) -> RetrievalResolution:
        context = case_context(workspace)
        scope = self._inspect(actor, context, as_of)
        guarded = _guard_scope(scope)
        if guarded is not None:
            return guarded
        query = build_policy_query(
            category=context["category"],
            issue=workspace.case.issue,
            request_summary=workspace.request.summary,
            products=context["products"],
            max_characters=self._query_character_limit,
        )
        search = self._store.search_hybrid_candidates(
            organization_public_id=actor.organization_id,
            profile_key=self._profile_key,
            case_category=context["category"],
            products=context["products"],
            region=context["region"],
            channel=context["channel"],
            customer_tier=context["tier"],
            as_of=as_of,
            query_text=query.text,
            query_embedding=self._embedding_provider.embed(query.text),
            candidate_limit=HYBRID_CANDIDATE_LIMIT,
        )
        guarded = _guard_scope(search)
        if guarded is not None:
            return guarded
        ranked = select_diverse(
            fuse_rankings(dense=search.dense, lexical=search.lexical)
        )
        if not ranked:
            return RetrievalResolution(
                EvidenceRetrievalStatus.MISSING,
                "No policy clause is relevant enough to cite.",
                [],
            )
        return RetrievalResolution(
            EvidenceRetrievalStatus.RELEVANT,
            "Recorded policy evidence is available.",
            _bindings(
                workspace=workspace,
                context=context,
                ranked=ranked,
                profile_key=self._profile_key,
                query_fingerprint=query.fingerprint,
                correlation_id=correlation_id,
            ),
        )

    def _inspect(
        self,
        actor: ActorContext,
        context: CaseRetrievalContext,
        as_of: datetime,
    ) -> HybridPolicyCandidatePage:
        return self._store.inspect_hybrid_scope(
            organization_public_id=actor.organization_id,
            profile_key=self._profile_key,
            case_category=context["category"],
            products=context["products"],
            region=context["region"],
            channel=context["channel"],
            customer_tier=context["tier"],
            as_of=as_of,
        )


def _guard_scope(scope: HybridPolicyCandidatePage) -> RetrievalResolution | None:
    states = (
        (scope.category_matches == 0, EvidenceRetrievalStatus.MISSING,
         "No published policy covers this case category."),
        (scope.applicable_matches == 0, EvidenceRetrievalStatus.INAPPLICABLE,
         "Published policies exist but do not match this case context."),
        (scope.active_matches == 0, EvidenceRetrievalStatus.STALE,
         "Matching policy versions are outside their effective dates."),
        (bool(scope.conflicting_scopes), EvidenceRetrievalStatus.CONFLICTING,
         "Multiple published policies claim the same decision scope."),
        (not scope.index_ready, EvidenceRetrievalStatus.MISSING,
         "Policy search is temporarily unavailable while its index is updated."),
    )
    for applies, status, reason in states:
        if applies:
            return RetrievalResolution(status, reason, [])
    return None


def _bindings(
    *,
    workspace: CaseWorkspaceRecord,
    context: CaseRetrievalContext,
    ranked: list[RankedClause],
    profile_key: str,
    query_fingerprint: str,
    correlation_id: str,
) -> list[PolicyEvidenceBinding]:
    bindings: list[PolicyEvidenceBinding] = []
    for item in ranked:
        candidate = item.candidate
        clause = candidate.clauses[0]
        applicability = context_label(context, candidate.version.decision_scope)
        fingerprint = sha256(
            "|".join(
                [
                    workspace.case.public_id,
                    candidate.policy.public_id,
                    candidate.version.content_hash,
                    clause.content_hash,
                    applicability,
                    profile_key,
                    RRF_ALGORITHM_VERSION,
                    query_fingerprint,
                ]
            ).encode()
        ).hexdigest()
        bindings.append(
            PolicyEvidenceBinding(
                policy=candidate.policy,
                version=candidate.version,
                clause=clause,
                retrieval_score=item.fused_score,
                applicability=applicability,
                fingerprint=fingerprint,
                embedding_profile_key=profile_key,
                retrieval_algorithm_version=RRF_ALGORITHM_VERSION,
                query_fingerprint=query_fingerprint,
                dense_rank=item.dense_rank,
                lexical_rank=item.lexical_rank,
                fused_retrieval_score=item.fused_score,
                retrieval_run_correlation_id=correlation_id,
            )
        )
    return bindings
