from datetime import UTC, datetime
from typing import Protocol

from app.domain.cases import CaseWorkspaceRecord
from app.domain.identity import ActorContext, Permission
from app.domain.policies import (
    EvidenceRetrievalResult,
    EvidenceRetrievalStatus,
    PolicyEvidenceBinding,
    PolicyEvidenceBundle,
    PolicyNotFound,
)
from app.retrieval.embeddings import DEFAULT_EMBEDDING_PROVIDER, EmbeddingProvider
from app.retrieval.governed_facade import GovernedPolicyRetrievalFacade
from app.retrieval.v1_governed import PolicyEvidenceSearchStore, V1PolicyRetrieval
from app.security.authorization import require_permission


class PolicyEvidenceStore(PolicyEvidenceSearchStore, Protocol):
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
        retrieval: GovernedPolicyRetrievalFacade | None = None,
    ) -> None:
        self._policy_store = policy_store
        self._case_store = case_store
        self._retrieval = retrieval or GovernedPolicyRetrievalFacade(
            v1=V1PolicyRetrieval(
                store=policy_store,
                embedding_provider=embedding_provider,
            )
        )

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
        workspace = self._workspace(actor=actor, case_id=case_id)
        status, reason, bindings = self._resolve_bindings(
            actor=actor,
            workspace=workspace,
            as_of=as_of or datetime.now(UTC),
            correlation_id=correlation_id,
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
        workspace = self._workspace(actor=actor, case_id=case_id)
        status, _, bindings = self._resolve_bindings(
            actor=actor,
            workspace=workspace,
            as_of=datetime.now(UTC),
            correlation_id="freshness-check",
        )
        if status is not expected.status:
            return False
        if status is not EvidenceRetrievalStatus.RELEVANT:
            return not expected.evidence
        return _binding_snapshot(bindings) == _evidence_snapshot(expected.evidence)

    def _workspace(self, *, actor: ActorContext, case_id: str) -> CaseWorkspaceRecord:
        workspace = self._case_store.get_workspace(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )
        if workspace is None:
            raise PolicyNotFound("The case was not found.")
        return workspace

    def _resolve_bindings(
        self,
        *,
        actor: ActorContext,
        workspace: CaseWorkspaceRecord,
        as_of: datetime,
        correlation_id: str = "retrieval",
    ) -> tuple[EvidenceRetrievalStatus, str, list[PolicyEvidenceBinding]]:
        resolution = self._retrieval.resolve(
            actor=actor,
            workspace=workspace,
            as_of=as_of,
            correlation_id=correlation_id,
        )
        return resolution.status, resolution.reason, resolution.bindings


def _evidence_snapshot(evidence: list[PolicyEvidenceBundle]) -> set[tuple[str, ...]]:
    return {
        (
            bundle.policy.public_id,
            bundle.version.public_id,
            bundle.version.content_hash,
            bundle.clause.public_id,
            bundle.clause.content_hash,
            bundle.evidence.fingerprint,
        )
        for bundle in evidence
    }


def _binding_snapshot(bindings: list[PolicyEvidenceBinding]) -> set[tuple[str, ...]]:
    return {
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
