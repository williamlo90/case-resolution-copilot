from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol, TypedDict

from app.domain.cases import CaseWorkspaceRecord
from app.domain.identity import ActorContext, Permission
from app.domain.policies import (
    EvidenceRetrievalResult,
    EvidenceRetrievalStatus,
    PolicyEvidenceBinding,
    PolicyEvidenceBundle,
    PolicyNotFound,
    PolicyRetrievalCandidatePage,
)
from app.retrieval.embeddings import (
    DEFAULT_EMBEDDING_PROVIDER,
    EmbeddingProvider,
)
from app.security.authorization import require_permission

RETRIEVAL_CANDIDATE_LIMIT = 64
RETRIEVAL_SCORE_THRESHOLD = 0.15


class CaseRetrievalContext(TypedDict):
    category: str
    products: set[str]
    region: str
    channel: str
    tier: str


class PolicyEvidenceStore(Protocol):
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

    def bind_evidence(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        bindings: list[PolicyEvidenceBinding],
        correlation_id: str,
    ) -> list[PolicyEvidenceBundle]: ...

    def list_evidence_for_case(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> list[PolicyEvidenceBundle]: ...


class CaseEvidenceStore(Protocol):
    def get_workspace(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> CaseWorkspaceRecord | None: ...


class PolicyEvidenceService:
    def __init__(
        self,
        policy_store: PolicyEvidenceStore,
        case_store: CaseEvidenceStore,
        embedding_provider: EmbeddingProvider = DEFAULT_EMBEDDING_PROVIDER,
    ) -> None:
        self._policy_store = policy_store
        self._case_store = case_store
        self._embedding_provider = embedding_provider

    def list_for_case(
        self,
        *,
        actor: ActorContext,
        case_id: str,
    ) -> list[PolicyEvidenceBundle]:
        require_permission(actor, Permission.CASE_READ)
        require_permission(actor, Permission.POLICY_READ)
        return self._policy_store.list_evidence_for_case(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )

    def refresh_for_case(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        correlation_id: str,
        as_of: datetime | None = None,
    ) -> EvidenceRetrievalResult:
        require_permission(actor, Permission.CASE_MANAGE)
        require_permission(actor, Permission.POLICY_READ)
        workspace = self._case_store.get_workspace(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )
        if workspace is None:
            raise PolicyNotFound("The case was not found.")
        status, reason, bindings = self._resolve_bindings(
            actor=actor,
            workspace=workspace,
            as_of=as_of or datetime.now(UTC),
        )
        if status is not EvidenceRetrievalStatus.RELEVANT:
            return EvidenceRetrievalResult(status=status, reason=reason, evidence=[])
        evidence = self._policy_store.bind_evidence(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            bindings=bindings,
            correlation_id=correlation_id,
        )
        return EvidenceRetrievalResult(
            status=EvidenceRetrievalStatus.RELEVANT,
            reason=reason,
            evidence=evidence,
        )

    def is_current_for_case(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected: EvidenceRetrievalResult,
    ) -> bool:
        require_permission(actor, Permission.CASE_MANAGE)
        require_permission(actor, Permission.POLICY_READ)
        workspace = self._case_store.get_workspace(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )
        if workspace is None:
            raise PolicyNotFound("The case was not found.")
        status, _, bindings = self._resolve_bindings(
            actor=actor,
            workspace=workspace,
            as_of=datetime.now(UTC),
        )
        if status is not expected.status:
            return False
        if status is not EvidenceRetrievalStatus.RELEVANT:
            return not expected.evidence
        expected_snapshot = {
            (
                bundle.policy.public_id,
                bundle.version.public_id,
                bundle.version.content_hash,
                bundle.clause.public_id,
                bundle.clause.content_hash,
                bundle.evidence.fingerprint,
            )
            for bundle in expected.evidence
        }
        current_snapshot = {
            (
                binding.policy.public_id,
                binding.version.public_id,
                binding.version.content_hash,
                binding.clause.public_id,
                binding.clause.content_hash,
                binding.fingerprint,
            )
            for binding in bindings
        }
        return current_snapshot == expected_snapshot

    def _resolve_bindings(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
        as_of: datetime,
    ) -> tuple[EvidenceRetrievalStatus, str, list[PolicyEvidenceBinding]]:
        context = _case_context(workspace)
        search = self._policy_store.search_retrieval_candidates(
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
        if search.category_matches == 0:
            return (
                EvidenceRetrievalStatus.MISSING,
                "No published policy covers this case category.",
                [],
            )
        if search.applicable_matches == 0:
            return (
                EvidenceRetrievalStatus.INAPPLICABLE,
                "Published policies exist but do not match this case context.",
                [],
            )
        if search.active_matches == 0:
            return (
                EvidenceRetrievalStatus.STALE,
                "Matching policy versions are outside their effective dates.",
                [],
            )
        if search.truncated:
            return (
                EvidenceRetrievalStatus.CONFLICTING,
                "Policy retrieval could not safely rule out a conflict.",
                [],
            )
        if search.conflicting_scopes:
            return (
                EvidenceRetrievalStatus.CONFLICTING,
                "Multiple published policies claim the same decision scope.",
                [],
            )

        bindings: list[PolicyEvidenceBinding] = []
        for ranked in search.candidates:
            candidate = ranked.candidate
            if not candidate.clauses or ranked.retrieval_score < RETRIEVAL_SCORE_THRESHOLD:
                continue
            clause = candidate.clauses[0]
            applicability_label = _context_label(
                context,
                candidate.version.decision_scope,
            )
            fingerprint = sha256(
                "|".join(
                    [
                        workspace.case.public_id,
                        candidate.policy.public_id,
                        str(candidate.version.version),
                        candidate.version.content_hash,
                        clause.content_hash,
                        applicability_label,
                    ]
                ).encode()
            ).hexdigest()
            bindings.append(
                PolicyEvidenceBinding(
                    policy=candidate.policy,
                    version=candidate.version,
                    clause=clause,
                    retrieval_score=ranked.retrieval_score,
                    applicability=applicability_label,
                    fingerprint=fingerprint,
                )
            )
        if not bindings:
            return (
                EvidenceRetrievalStatus.MISSING,
                "No policy clause is relevant enough to cite.",
                [],
            )
        return (
            EvidenceRetrievalStatus.RELEVANT,
            "Recorded policy evidence is available.",
            bindings,
        )


def _case_context(workspace: CaseWorkspaceRecord) -> CaseRetrievalContext:
    products = {
        str(context.fields["product"]).strip().lower()
        for context in workspace.business_contexts
        if context.fields.get("product")
    }
    locale_parts = workspace.customer.locale.replace("_", "-").split("-")
    region = locale_parts[-1].lower() if len(locale_parts) > 1 else "unknown"
    return {
        "category": workspace.case.category.value,
        "products": products or {"unknown"},
        "region": region,
        "channel": workspace.request.channel.value,
        "tier": workspace.customer.tier.value,
    }


def _context_label(
    context: CaseRetrievalContext,
    decision_scope: str,
) -> str:
    products = ", ".join(sorted(context["products"]))
    return (
        f"{decision_scope}; category {context['category']}; products {products}; "
        f"region {context['region']}; channel {context['channel']}; tier {context['tier']}"
    )
