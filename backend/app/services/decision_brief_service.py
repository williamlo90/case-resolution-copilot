from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from app.analysis.deterministic_decision_engine import (
    DecisionEngine,
    combined_context_fingerprint,
    combined_evidence_fingerprint,
    context_snapshot_fingerprint,
    decision_input_fingerprint,
)
from app.domain.cases import CaseConcurrencyConflict, CaseStatus, CaseWorkspaceRecord
from app.domain.decision_briefs import (
    AnalysisStatus,
    CompletedDecisionGeneration,
    ContextSnapshotReference,
    DecisionAnalysis,
    DecisionBriefCreate,
    DecisionBriefRecord,
    DecisionFingerprintRetryExhausted,
    DecisionGenerationLease,
    EvidenceSnapshotReference,
    ProposalGenerationNotAllowed,
    ProposalNotFound,
    ProposalSnapshotMismatch,
)
from app.domain.identity import ActorContext, Permission
from app.domain.policies import EvidenceRetrievalResult
from app.security.authorization import require_permission

DECISION_GENERATION_LEASE_SECONDS = 60
MAX_DECISION_GENERATION_ATTEMPTS = 3
MAX_INPUT_FINGERPRINT_RETRIES = 3


class DecisionBriefStore(Protocol):
    def get_by_input_fingerprint(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        input_fingerprint: str,
    ) -> DecisionBriefRecord | None: ...

    def get_latest(
        self, *, organization_public_id: str, case_public_id: str
    ) -> DecisionBriefRecord | None: ...

    def get_version(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        version: int,
    ) -> DecisionBriefRecord | None: ...

    def create_or_get(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        command: DecisionBriefCreate,
        correlation_id: str,
    ) -> DecisionBriefRecord: ...


class DecisionCaseStore(Protocol):
    def get_workspace(
        self, *, organization_public_id: str, case_public_id: str
    ) -> CaseWorkspaceRecord | None: ...


class PolicyEvidenceResolver(Protocol):
    def refresh_for_case(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        correlation_id: str,
    ) -> EvidenceRetrievalResult: ...

    def is_current_for_case(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected: EvidenceRetrievalResult,
    ) -> bool: ...


class DecisionGenerationStore(Protocol):
    def acquire(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        input_fingerprint: str,
        lease_seconds: int,
        max_attempts: int,
    ) -> DecisionGenerationLease | CompletedDecisionGeneration: ...

    def complete(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        lease: DecisionGenerationLease,
        analysis_run_id: UUID,
    ) -> None: ...

    def fail(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        lease: DecisionGenerationLease,
        error_code: str,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class DecisionBriefGenerationPlan:
    workspace: CaseWorkspaceRecord
    evidence: EvidenceRetrievalResult
    expected_case_version: int
    input_fingerprint: str
    context_fingerprint: str
    evidence_fingerprint: str
    lease: DecisionGenerationLease


class DecisionBriefService:
    def __init__(
        self,
        store: DecisionBriefStore,
        case_store: DecisionCaseStore,
        evidence_resolver: PolicyEvidenceResolver,
        engine: DecisionEngine,
        generation_store: DecisionGenerationStore,
    ) -> None:
        self._store = store
        self._case_store = case_store
        self._evidence_resolver = evidence_resolver
        self._engine = engine
        self._generation_store = generation_store

    def generate(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_case_version: int,
        correlation_id: str,
    ) -> DecisionBriefRecord:
        prepared = self.prepare_generation(
            actor=actor,
            case_id=case_id,
            expected_case_version=expected_case_version,
            correlation_id=correlation_id,
        )
        if not isinstance(prepared, DecisionBriefGenerationPlan):
            return prepared
        try:
            analysis = self._engine.analyze(
                workspace=prepared.workspace,
                evidence=prepared.evidence,
                input_fingerprint=prepared.input_fingerprint,
            )
            return self.persist_generation(
                actor=actor,
                case_id=case_id,
                preparation=prepared,
                analysis=analysis,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            self.release_generation(
                actor=actor,
                case_id=case_id,
                preparation=prepared,
                error_code=type(exc).__name__,
            )
            raise

    def prepare_generation(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_case_version: int,
        correlation_id: str,
    ) -> DecisionBriefGenerationPlan | DecisionBriefRecord:
        require_permission(actor, Permission.CASE_MANAGE)
        require_permission(actor, Permission.POLICY_READ)
        workspace = self._case_store.get_workspace(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )
        if workspace is None:
            raise ProposalNotFound("The case was not found.")
        if workspace.case.version != expected_case_version:
            raise CaseConcurrencyConflict(
                expected_version=expected_case_version,
                current_version=workspace.case.version,
            )
        if workspace.case.status is CaseStatus.COMPLETED:
            raise ProposalGenerationNotAllowed(
                "A completed case must be reopened before its decision brief can be revised."
            )
        evidence = self._evidence_resolver.refresh_for_case(
            actor=actor,
            case_id=case_id,
            correlation_id=correlation_id,
        )
        context_fingerprint = combined_context_fingerprint(workspace)
        evidence_fingerprint = combined_evidence_fingerprint(evidence)
        base_input_fingerprint = decision_input_fingerprint(
            workspace=workspace,
            evidence=evidence,
            context_fingerprint=context_fingerprint,
            evidence_fingerprint=evidence_fingerprint,
            model_version=self._engine.model_version,
            prompt_version=self._engine.prompt_version,
            graph_version=self._engine.graph_version,
            risk_rule_version=self._engine.risk_rule_version,
        )
        input_fingerprint = base_input_fingerprint
        for retry_number in range(MAX_INPUT_FINGERPRINT_RETRIES + 1):
            existing = self._store.get_by_input_fingerprint(
                organization_public_id=actor.organization_id,
                case_public_id=case_id,
                input_fingerprint=input_fingerprint,
            )
            if existing is None:
                break
            if _can_reuse(existing, model_version=self._engine.model_version):
                return existing
            input_fingerprint = _retry_input_fingerprint(
                base_input_fingerprint,
                retry_number=retry_number + 1,
            )
        else:
            raise DecisionFingerprintRetryExhausted(
                "Decision brief retry fingerprints are exhausted for this snapshot."
            )
        reservation = self._generation_store.acquire(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            input_fingerprint=input_fingerprint,
            lease_seconds=DECISION_GENERATION_LEASE_SECONDS,
            max_attempts=MAX_DECISION_GENERATION_ATTEMPTS,
        )
        if isinstance(reservation, CompletedDecisionGeneration):
            completed = self._store.get_by_input_fingerprint(
                organization_public_id=actor.organization_id,
                case_public_id=case_id,
                input_fingerprint=reservation.input_fingerprint,
            )
            if completed is None or completed.run.id != reservation.analysis_run_id:
                raise ProposalSnapshotMismatch(
                    "The completed generation is missing its immutable decision brief."
                )
            return completed
        return DecisionBriefGenerationPlan(
            workspace=workspace,
            evidence=evidence,
            expected_case_version=expected_case_version,
            input_fingerprint=input_fingerprint,
            context_fingerprint=context_fingerprint,
            evidence_fingerprint=evidence_fingerprint,
            lease=reservation,
        )

    def persist_generation(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        preparation: DecisionBriefGenerationPlan,
        analysis: DecisionAnalysis,
        correlation_id: str,
    ) -> DecisionBriefRecord:
        require_permission(actor, Permission.CASE_MANAGE)
        require_permission(actor, Permission.POLICY_READ)
        if not self._evidence_resolver.is_current_for_case(
            actor=actor,
            case_id=case_id,
            expected=preparation.evidence,
        ):
            raise ProposalSnapshotMismatch(
                "Applicable policy evidence changed while the decision brief was generated."
            )
        command = DecisionBriefCreate(
            expected_case_version=preparation.expected_case_version,
            input_fingerprint=preparation.input_fingerprint,
            context_fingerprint=preparation.context_fingerprint,
            evidence_fingerprint=preparation.evidence_fingerprint,
            analysis=analysis,
            evidence=[
                EvidenceSnapshotReference(
                    public_id=bundle.evidence.public_id,
                    fingerprint=bundle.evidence.fingerprint,
                )
                for bundle in preparation.evidence.evidence
            ],
            contexts=[
                ContextSnapshotReference(
                    public_id=context.public_id,
                    version=context.version,
                    fingerprint=context_snapshot_fingerprint(context),
                )
                for context in preparation.workspace.business_contexts
            ],
        )
        brief = self._store.create_or_get(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            actor_id=actor.actor_id,
            actor_type=actor.kind.value,
            command=command,
            correlation_id=correlation_id,
        )
        self._generation_store.complete(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            lease=preparation.lease,
            analysis_run_id=brief.run.id,
        )
        return brief

    def release_generation(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        preparation: DecisionBriefGenerationPlan,
        error_code: str,
    ) -> bool:
        return self._generation_store.fail(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            lease=preparation.lease,
            error_code=error_code,
        )

    def get_latest(self, *, actor: ActorContext, case_id: str) -> DecisionBriefRecord:
        require_permission(actor, Permission.CASE_READ)
        brief = self._store.get_latest(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
        )
        if brief is None:
            raise ProposalNotFound("No decision brief has been generated for this case.")
        return brief

    def get_version(
        self, *, actor: ActorContext, case_id: str, version: int
    ) -> DecisionBriefRecord:
        require_permission(actor, Permission.CASE_READ)
        brief = self._store.get_version(
            organization_public_id=actor.organization_id,
            case_public_id=case_id,
            version=version,
        )
        if brief is None:
            raise ProposalNotFound("The proposal version was not found.")
        return brief


def _can_reuse(brief: DecisionBriefRecord, *, model_version: str) -> bool:
    return brief.run.status is AnalysisStatus.ABSTAINED or brief.run.model_version == model_version


def _retry_input_fingerprint(
    base_input_fingerprint: str,
    *,
    retry_number: int,
) -> str:
    return sha256(f"{base_input_fingerprint}:ai-retry:{retry_number}".encode()).hexdigest()
