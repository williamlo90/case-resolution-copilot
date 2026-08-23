from datetime import datetime
from hashlib import sha256
from typing import Protocol

from app.domain.cases import CaseWorkspaceRecord
from app.domain.identity import ActorContext
from app.domain.policies import (
    EvidenceRetrievalStatus,
    PolicyEvidenceBinding,
    PolicyRetrievalCandidatePage,
)
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.governed_facade import RetrievalResolution
from app.retrieval.policy_context import (
    CaseRetrievalContext,
    case_context,
    context_label,
)

RETRIEVAL_CANDIDATE_LIMIT = 64
RETRIEVAL_SCORE_THRESHOLD = 0.15


class PolicyEvidenceSearchStore(Protocol):
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
    ) -> PolicyRetrievalCandidatePage: ...


class V1PolicyRetrieval:
    def __init__(
        self,
        *,
        store: PolicyEvidenceSearchStore,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._store = store
        self._embedding_provider = embedding_provider

    def resolve(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
        as_of: datetime,
        correlation_id: str,
    ) -> RetrievalResolution:
        del correlation_id
        context = case_context(workspace)
        search = self._store.search_retrieval_candidates(
            organization_public_id=actor.organization_id,
            case_category=context["category"],
            products=context["products"],
            region=context["region"],
            channel=context["channel"],
            customer_tier=context["tier"],
            as_of=as_of,
            query_embedding=self._embedding_provider.embed(
                f"{workspace.case.issue} {workspace.request.summary}"
            ),
            embedding_version=self._embedding_provider.version,
            candidate_limit=RETRIEVAL_CANDIDATE_LIMIT,
        )
        guarded = _guard_search(search)
        if guarded is not None:
            return guarded
        bindings = _bindings(workspace, context, search)
        if not bindings:
            return RetrievalResolution(
                EvidenceRetrievalStatus.MISSING,
                "No policy clause is relevant enough to cite.",
                [],
            )
        return RetrievalResolution(
            EvidenceRetrievalStatus.RELEVANT,
            "Recorded policy evidence is available.",
            bindings,
        )


def _guard_search(search: PolicyRetrievalCandidatePage) -> RetrievalResolution | None:
    states = (
        (
            search.category_matches == 0,
            EvidenceRetrievalStatus.MISSING,
            "No published policy covers this case category.",
        ),
        (
            search.applicable_matches == 0,
            EvidenceRetrievalStatus.INAPPLICABLE,
            "Published policies exist but do not match this case context.",
        ),
        (
            search.active_matches == 0,
            EvidenceRetrievalStatus.STALE,
            "Matching policy versions are outside their effective dates.",
        ),
        (
            search.truncated,
            EvidenceRetrievalStatus.CONFLICTING,
            "Policy retrieval could not safely rule out a conflict.",
        ),
        (
            bool(search.conflicting_scopes),
            EvidenceRetrievalStatus.CONFLICTING,
            "Multiple published policies claim the same decision scope.",
        ),
    )
    for applies, status, reason in states:
        if applies:
            return RetrievalResolution(status, reason, [])
    return None


def _bindings(
    workspace: CaseWorkspaceRecord,
    context: CaseRetrievalContext,
    search: PolicyRetrievalCandidatePage,
) -> list[PolicyEvidenceBinding]:
    bindings: list[PolicyEvidenceBinding] = []
    for ranked in search.candidates:
        candidate = ranked.candidate
        if not candidate.clauses or ranked.retrieval_score < RETRIEVAL_SCORE_THRESHOLD:
            continue
        clause = candidate.clauses[0]
        applicability = context_label(context, candidate.version.decision_scope)
        fingerprint = sha256(
            "|".join(
                [
                    workspace.case.public_id,
                    candidate.policy.public_id,
                    str(candidate.version.version),
                    candidate.version.content_hash,
                    clause.content_hash,
                    applicability,
                ]
            ).encode()
        ).hexdigest()
        bindings.append(
            PolicyEvidenceBinding(
                policy=candidate.policy,
                version=candidate.version,
                clause=clause,
                retrieval_score=ranked.retrieval_score,
                applicability=applicability,
                fingerprint=fingerprint,
            )
        )
    return bindings

