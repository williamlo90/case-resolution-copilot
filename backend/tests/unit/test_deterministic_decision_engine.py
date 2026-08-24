from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.analysis.deterministic_decision_engine import (
    DeterministicDecisionEngine,
    combined_context_fingerprint,
    combined_evidence_fingerprint,
    decision_input_fingerprint,
)
from app.domain.cases import (
    BusinessObjectRecord,
    BusinessObjectType,
    CaseCollectionWindowRecord,
    CaseConcurrencyConflict,
    CaseRecord,
    CaseRequestRecord,
    CaseStatus,
    CaseWorkspaceCollectionsRecord,
    CaseWorkspaceRecord,
    ConversationThreadRecord,
    CustomerContextRecord,
    SourceFreshness,
)
from app.domain.decision_briefs import (
    AnalysisStatus,
    CompletedDecisionGeneration,
    DecisionAnalysis,
    DecisionBriefCreate,
    DecisionBriefRecord,
    DecisionFingerprintRetryExhausted,
    DecisionGenerationLease,
    DecisionProposalState,
    ProposalConfidence,
    ProposalGenerationNotAllowed,
    ProposalSnapshotMismatch,
    RiskOutcome,
)
from app.domain.policies import EvidenceRetrievalResult, EvidenceRetrievalStatus
from app.integrations.case_source_simulator import DeterministicCaseSourceSimulator
from app.security.authentication import DeterministicAuthProvider
from app.security.authorization import PermissionDenied
from app.services.decision_brief_service import DecisionBriefService
from tests.builders import valid_decision_brief


def _workspace(case_id: str) -> CaseWorkspaceRecord:
    seed = next(
        item
        for item in DeterministicCaseSourceSimulator().fetch_cases()
        if item.public_id == case_id
    )
    organization_id = uuid4()
    internal_case_id = uuid4()
    return CaseWorkspaceRecord(
        case=CaseRecord(
            id=internal_case_id,
            public_id=seed.public_id,
            organization_id=organization_id,
            legacy_task_id=None,
            source_id=seed.source_id,
            external_reference=seed.external_reference,
            category=seed.category,
            issue=seed.issue,
            status=seed.status,
            owner_id=None,
            urgency=seed.urgency,
            risk=seed.risk,
            due_at=seed.due_at,
            impact_amount=seed.impact_amount,
            impact_currency=seed.impact_currency,
            source_freshness=seed.source_freshness,
            source_checked_at=seed.source_checked_at,
            version=1,
            created_at=seed.request.received_at,
            updated_at=seed.request.received_at,
        ),
        request=CaseRequestRecord(
            id=uuid4(),
            public_id=f"REQ-{seed.public_id}",
            organization_id=organization_id,
            case_id=internal_case_id,
            channel=seed.request.channel,
            customer_message=seed.request.customer_message,
            summary=seed.request.summary,
            received_at=seed.request.received_at,
        ),
        customer=CustomerContextRecord(
            id=uuid4(),
            organization_id=organization_id,
            case_id=internal_case_id,
            customer_id=seed.customer.customer_id,
            name=seed.customer.name,
            tier=seed.customer.tier,
            locale=seed.customer.locale,
            contact=seed.customer.contact,
            captured_at=seed.request.received_at,
        ),
        business_contexts=[
            BusinessObjectRecord(
                id=uuid4(),
                public_id=context.public_id,
                organization_id=organization_id,
                case_id=internal_case_id,
                type=context.type,
                label=context.label,
                source=context.source,
                source_reference=context.source_reference,
                status=context.status,
                fields=context.fields,
                captured_at=context.captured_at,
                source_freshness=context.freshness,
                source_checked_at=context.checked_at,
                version=1,
            )
            for context in seed.business_contexts
        ],
        owner=None,
        thread=ConversationThreadRecord(
            id=uuid4(),
            public_id=f"CV-{seed.public_id}",
            organization_id=organization_id,
            case_id=internal_case_id,
            version=1,
            updated_at=seed.request.received_at,
        ),
        messages=[],
        draft=None,
        activity=[],
        collections=CaseWorkspaceCollectionsRecord(
            business_contexts=CaseCollectionWindowRecord(
                returned=len(seed.business_contexts),
                total=len(seed.business_contexts),
                has_more=False,
            ),
            messages=CaseCollectionWindowRecord(
                returned=0,
                total=0,
                has_more=False,
            ),
            activity=CaseCollectionWindowRecord(
                returned=0,
                total=0,
                has_more=False,
            ),
        ),
    )


def _evidence(status: EvidenceRetrievalStatus) -> EvidenceRetrievalResult:
    return EvidenceRetrievalResult(
        status=status,
        reason=f"Deterministic evidence status: {status.value}.",
        evidence=[],
    )


def _analyze(
    case_id: str,
    status: EvidenceRetrievalStatus = EvidenceRetrievalStatus.RELEVANT,
) -> DecisionAnalysis:
    workspace = _workspace(case_id)
    evidence = _evidence(status)
    context_fingerprint = combined_context_fingerprint(workspace)
    evidence_fingerprint = combined_evidence_fingerprint(evidence)
    input_fingerprint = decision_input_fingerprint(
        workspace=workspace,
        evidence=evidence,
        context_fingerprint=context_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
    return DeterministicDecisionEngine().analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint=input_fingerprint,
    )


def test_refund_case_produces_reviewable_evidence_bound_resolution() -> None:
    result = _analyze("CS-2047")

    assert result.status is AnalysisStatus.COMPLETED
    assert result.state is DecisionProposalState.READY_FOR_REVIEW
    assert result.confidence is ProposalConfidence.MEDIUM
    assert result.missing_information == []
    assert result.impact_amount is not None
    assert result.proposed_actions[0].type == "issue_refund"
    assert result.proposed_actions[0].review_required is True
    assert any(risk.outcome is RiskOutcome.REQUIRES_REVIEW for risk in result.risks)
    assert len(result.checkpoints) == 4
    assert result.response_draft.subject == "Update on your refund request"
    assert result.response_draft.body.startswith("Hello Marcus Lee,")
    assert "service order is unused and delivery has not started" in (result.response_draft.body)
    assert "The refund remains pending and has not been issued" in result.response_draft.body


def test_billing_case_does_not_infer_duplicate_settlement_from_attempt_count() -> None:
    result = _analyze("CS-2048")

    assert result.state is DecisionProposalState.INFORMATION_NEEDED
    assert result.confidence is ProposalConfidence.LOW
    assert {gap.label for gap in result.missing_information} == {"Second payment reference"}
    assert result.impact_amount is None
    assert result.proposed_actions[0].type == "request_information"
    assert result.response_draft.status.value == "blocked"
    assert result.response_draft.subject == "Information needed for your billing case"
    assert result.response_draft.body.startswith("Hello Nadia Prasetyo,")
    assert "one captured payment record, not two settled charges" in (result.response_draft.body)
    assert "second settled payment reference" in result.response_draft.body
    assert "before considering any billing adjustment" in result.response_draft.body
    assert "We received your request" not in result.response_draft.body


def test_billing_case_requires_two_settled_payment_references() -> None:
    workspace = _workspace("CS-2048")
    first_payment = workspace.business_contexts[0]
    workspace.business_contexts.append(
        BusinessObjectRecord(
            id=uuid4(),
            public_id="CTX-PAY-PENDING",
            organization_id=workspace.case.organization_id,
            case_id=workspace.case.id,
            type=BusinessObjectType.PAYMENT,
            label="Second payment attempt",
            source="Billing system",
            source_reference="PAY-PENDING-02",
            status="pending",
            fields={"amount": "49.00", "currency": "USD"},
            captured_at=first_payment.captured_at,
            source_freshness=SourceFreshness.CURRENT,
            source_checked_at=first_payment.source_checked_at,
            version=1,
        )
    )
    workspace.collections.business_contexts.returned += 1
    workspace.collections.business_contexts.total += 1
    evidence = _evidence(EvidenceRetrievalStatus.RELEVANT)
    result = DeterministicDecisionEngine().analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint=decision_input_fingerprint(
            workspace=workspace,
            evidence=evidence,
            context_fingerprint=combined_context_fingerprint(workspace),
            evidence_fingerprint=combined_evidence_fingerprint(evidence),
        ),
    )

    assert result.state is DecisionProposalState.INFORMATION_NEEDED
    assert {gap.label for gap in result.missing_information} == {"Second payment reference"}


def test_stale_account_context_requires_refresh_and_identity_verification() -> None:
    result = _analyze("CS-2046")

    assert result.state is DecisionProposalState.INFORMATION_NEEDED
    assert {gap.label for gap in result.missing_information} == {
        "Current source context",
        "Identity verification",
    }
    assert any(risk.outcome is RiskOutcome.INFORMATION_NEEDED for risk in result.risks)


def test_missing_policy_abstains_without_consequential_action() -> None:
    result = _analyze("CS-2047", EvidenceRetrievalStatus.MISSING)

    assert result.status is AnalysisStatus.ABSTAINED
    assert result.state is DecisionProposalState.INFORMATION_NEEDED
    assert result.confidence is ProposalConfidence.LOW
    assert result.proposed_actions[0].type == "request_information"
    assert result.proposed_actions[0].review_required is False
    assert result.checkpoints[1].status.value == "abstained"


def test_truncated_business_context_blocks_a_final_resolution() -> None:
    workspace = _workspace("CS-2047")
    returned = len(workspace.business_contexts)
    workspace.collections.business_contexts = CaseCollectionWindowRecord(
        returned=returned,
        total=returned + 1,
        has_more=True,
    )
    evidence = _evidence(EvidenceRetrievalStatus.RELEVANT)

    result = DeterministicDecisionEngine().analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint="f" * 64,
    )

    assert result.state is DecisionProposalState.INFORMATION_NEEDED
    assert "Complete business records" in {gap.label for gap in result.missing_information}
    assert all(action.review_required is False for action in result.proposed_actions)


def test_input_fingerprint_changes_with_case_version() -> None:
    workspace = _workspace("CS-2047")
    evidence = _evidence(EvidenceRetrievalStatus.RELEVANT)
    context_fingerprint = combined_context_fingerprint(workspace)
    evidence_fingerprint = combined_evidence_fingerprint(evidence)
    first = decision_input_fingerprint(
        workspace=workspace,
        evidence=evidence,
        context_fingerprint=context_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
    changed = workspace.model_copy(
        update={"case": workspace.case.model_copy(update={"version": 2})}
    )
    second = decision_input_fingerprint(
        workspace=changed,
        evidence=evidence,
        context_fingerprint=context_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
    provider_changed = decision_input_fingerprint(
        workspace=workspace,
        evidence=evidence,
        context_fingerprint=context_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        model_version="openai:gpt-5.6-luna",
        prompt_version="openai-decision-narrative-v2",
    )

    assert first != second
    assert first != provider_changed


class _BriefStore:
    def __init__(self) -> None:
        self.command: DecisionBriefCreate | None = None
        self.result = valid_decision_brief()
        self.lookup_results: list[DecisionBriefRecord | None] = []
        self.input_fingerprints: list[str] = []

    def get_by_input_fingerprint(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        input_fingerprint: str,
    ) -> DecisionBriefRecord | None:
        del organization_public_id, case_public_id
        self.input_fingerprints.append(input_fingerprint)
        return self.lookup_results.pop(0) if self.lookup_results else None

    def get_latest(
        self, *, organization_public_id: str, case_public_id: str
    ) -> DecisionBriefRecord | None:
        del organization_public_id, case_public_id
        return self.result

    def get_version(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        version: int,
    ) -> DecisionBriefRecord | None:
        del organization_public_id, case_public_id, version
        return self.result

    def create_or_get(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        actor_type: str,
        command: DecisionBriefCreate,
        correlation_id: str,
    ) -> DecisionBriefRecord:
        del organization_public_id, case_public_id, actor_id, actor_type, correlation_id
        self.command = command
        return self.result


class _CaseStore:
    def __init__(self, workspace: CaseWorkspaceRecord | None) -> None:
        self.workspace = workspace

    def get_workspace(
        self, *, organization_public_id: str, case_public_id: str
    ) -> CaseWorkspaceRecord | None:
        del organization_public_id, case_public_id
        return self.workspace


class _EvidenceResolver:
    def __init__(
        self,
        result: EvidenceRetrievalResult,
        *,
        current: bool = True,
    ) -> None:
        self.result = result
        self.calls = 0
        self.current = current
        self.current_checks = 0

    def refresh_for_case(
        self,
        *,
        actor: object,
        case_id: str,
        correlation_id: str,
    ) -> EvidenceRetrievalResult:
        del actor, case_id, correlation_id
        self.calls += 1
        return self.result

    def is_current_for_case(
        self,
        *,
        actor: object,
        case_id: str,
        expected: EvidenceRetrievalResult,
    ) -> bool:
        del actor, case_id, expected
        self.current_checks += 1
        return self.current


class _GenerationStore:
    def __init__(self, *, completed_run_id: UUID | None = None) -> None:
        self.acquisitions = 0
        self.completed_run_id: UUID | None = None
        self.failure_code: str | None = None
        self.reserved_completed_run_id = completed_run_id

    def acquire(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        input_fingerprint: str,
        lease_seconds: int,
        max_attempts: int,
    ) -> DecisionGenerationLease | CompletedDecisionGeneration:
        del organization_public_id, case_public_id, max_attempts
        self.acquisitions += 1
        if self.reserved_completed_run_id is not None:
            return CompletedDecisionGeneration(
                input_fingerprint=input_fingerprint,
                analysis_run_id=self.reserved_completed_run_id,
            )
        return DecisionGenerationLease(
            input_fingerprint=input_fingerprint,
            owner_token=uuid4(),
            fence_token=1,
            attempt=1,
            expires_at=datetime.now(UTC) + timedelta(seconds=lease_seconds),
        )

    def complete(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        lease: DecisionGenerationLease,
        analysis_run_id: UUID,
    ) -> None:
        del organization_public_id, case_public_id, lease
        self.completed_run_id = analysis_run_id

    def fail(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        lease: DecisionGenerationLease,
        error_code: str,
    ) -> bool:
        del organization_public_id, case_public_id, lease
        self.failure_code = error_code
        return True


class _CountingDecisionEngine(DeterministicDecisionEngine):
    def __init__(self) -> None:
        self.calls = 0

    def analyze(
        self,
        *,
        workspace: CaseWorkspaceRecord,
        evidence: EvidenceRetrievalResult,
        input_fingerprint: str,
    ) -> DecisionAnalysis:
        self.calls += 1
        return super().analyze(
            workspace=workspace,
            evidence=evidence,
            input_fingerprint=input_fingerprint,
        )


def _existing_brief(
    *,
    status: AnalysisStatus,
    model_version: str,
) -> DecisionBriefRecord:
    return valid_decision_brief(
        analysis_status=status,
        model_version=model_version,
    )


def test_service_builds_server_owned_snapshot_references() -> None:
    workspace = _workspace("CS-2047")
    store = _BriefStore()
    resolver = _EvidenceResolver(_evidence(EvidenceRetrievalStatus.RELEVANT))
    service = DecisionBriefService(
        store,
        _CaseStore(workspace),
        resolver,
        DeterministicDecisionEngine(),
        _GenerationStore(),
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.generate(
        actor=actor,
        case_id=workspace.case.public_id,
        expected_case_version=1,
        correlation_id="corr-test",
    )

    assert result is store.result
    assert resolver.calls == 1
    assert store.command is not None
    assert len(store.command.contexts) == len(workspace.business_contexts)
    assert store.command.contexts[0].public_id in {
        context.public_id for context in workspace.business_contexts
    }
    assert len(store.command.input_fingerprint) == 64


def test_service_records_an_empty_context_snapshot_for_an_inbox_case() -> None:
    workspace = _workspace("CS-2048")
    workspace.business_contexts = []
    workspace.collections.business_contexts = CaseCollectionWindowRecord(
        returned=0,
        total=0,
        has_more=False,
    )
    store = _BriefStore()
    service = DecisionBriefService(
        store,
        _CaseStore(workspace),
        _EvidenceResolver(_evidence(EvidenceRetrievalStatus.MISSING)),
        DeterministicDecisionEngine(),
        _GenerationStore(),
    )

    service.generate(
        actor=DeterministicAuthProvider().authenticate("USR-0001"),
        case_id=workspace.case.public_id,
        expected_case_version=1,
        correlation_id="corr-inbox-context",
    )

    assert store.command is not None
    assert store.command.contexts == []
    assert store.command.analysis.status is AnalysisStatus.ABSTAINED
    assert store.command.analysis.state is DecisionProposalState.INFORMATION_NEEDED
    assert store.command.analysis.proposed_actions[0].type == "request_information"


def test_service_reuses_an_identical_brief_before_running_the_model() -> None:
    workspace = _workspace("CS-2047")
    store = _BriefStore()
    resolver = _EvidenceResolver(_evidence(EvidenceRetrievalStatus.RELEVANT))
    engine = _CountingDecisionEngine()
    existing = _existing_brief(
        status=AnalysisStatus.COMPLETED,
        model_version=engine.model_version,
    )
    store.lookup_results = [existing]
    service = DecisionBriefService(
        store,
        _CaseStore(workspace),
        resolver,
        engine,
        _GenerationStore(),
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.generate(
        actor=actor,
        case_id=workspace.case.public_id,
        expected_case_version=1,
        correlation_id="corr-test",
    )

    assert result is existing
    assert resolver.calls == 1
    assert engine.calls == 0
    assert store.command is None


def test_service_reuses_a_generation_that_completed_during_reservation() -> None:
    workspace = _workspace("CS-2047")
    store = _BriefStore()
    resolver = _EvidenceResolver(_evidence(EvidenceRetrievalStatus.RELEVANT))
    engine = _CountingDecisionEngine()
    existing = _existing_brief(
        status=AnalysisStatus.COMPLETED,
        model_version=engine.model_version,
    )
    store.lookup_results = [None, existing]
    generation_store = _GenerationStore(completed_run_id=existing.run.id)
    service = DecisionBriefService(
        store,
        _CaseStore(workspace),
        resolver,
        engine,
        generation_store,
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.generate(
        actor=actor,
        case_id=workspace.case.public_id,
        expected_case_version=1,
        correlation_id="corr-test",
    )

    assert result is existing
    assert generation_store.acquisitions == 1
    assert engine.calls == 0
    assert store.command is None


def test_service_retries_a_temporary_model_fallback_with_a_new_fingerprint() -> None:
    workspace = _workspace("CS-2047")
    store = _BriefStore()
    engine = _CountingDecisionEngine()
    store.lookup_results = [
        _existing_brief(
            status=AnalysisStatus.COMPLETED,
            model_version=f"{engine.model_version}:fallback",
        ),
        None,
    ]
    resolver = _EvidenceResolver(_evidence(EvidenceRetrievalStatus.RELEVANT))
    service = DecisionBriefService(
        store,
        _CaseStore(workspace),
        resolver,
        engine,
        _GenerationStore(),
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    result = service.generate(
        actor=actor,
        case_id=workspace.case.public_id,
        expected_case_version=1,
        correlation_id="corr-test",
    )

    assert result is store.result
    assert engine.calls == 1
    assert store.command is not None
    assert len(store.input_fingerprints) == 2
    assert store.input_fingerprints[0] != store.input_fingerprints[1]
    assert store.command.input_fingerprint == store.input_fingerprints[1]


def test_service_bounds_incompatible_fingerprint_retries() -> None:
    workspace = _workspace("CS-2047")
    store = _BriefStore()
    engine = _CountingDecisionEngine()
    store.lookup_results = [
        _existing_brief(
            status=AnalysisStatus.COMPLETED,
            model_version=f"{engine.model_version}:fallback:{index}",
        )
        for index in range(4)
    ]
    generation_store = _GenerationStore()
    service = DecisionBriefService(
        store,
        _CaseStore(workspace),
        _EvidenceResolver(_evidence(EvidenceRetrievalStatus.RELEVANT)),
        engine,
        generation_store,
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(DecisionFingerprintRetryExhausted):
        service.generate(
            actor=actor,
            case_id=workspace.case.public_id,
            expected_case_version=1,
            correlation_id="corr-test",
        )

    assert len(store.input_fingerprints) == 4
    assert generation_store.acquisitions == 0
    assert engine.calls == 0


def test_service_rejects_policy_changes_before_persisting_model_output() -> None:
    workspace = _workspace("CS-2047")
    store = _BriefStore()
    resolver = _EvidenceResolver(
        _evidence(EvidenceRetrievalStatus.RELEVANT),
        current=False,
    )
    generation_store = _GenerationStore()
    service = DecisionBriefService(
        store,
        _CaseStore(workspace),
        resolver,
        _CountingDecisionEngine(),
        generation_store,
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(ProposalSnapshotMismatch):
        service.generate(
            actor=actor,
            case_id=workspace.case.public_id,
            expected_case_version=1,
            correlation_id="corr-test",
        )

    assert resolver.current_checks == 1
    assert store.command is None
    assert generation_store.failure_code == "ProposalSnapshotMismatch"


def test_service_rejects_stale_case_before_policy_refresh() -> None:
    workspace = _workspace("CS-2047")
    resolver = _EvidenceResolver(_evidence(EvidenceRetrievalStatus.RELEVANT))
    service = DecisionBriefService(
        _BriefStore(),
        _CaseStore(workspace),
        resolver,
        DeterministicDecisionEngine(),
        _GenerationStore(),
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(CaseConcurrencyConflict):
        service.generate(
            actor=actor,
            case_id=workspace.case.public_id,
            expected_case_version=2,
            correlation_id="corr-test",
        )

    assert resolver.calls == 0


def test_service_rejects_completed_case_and_read_only_actor() -> None:
    workspace = _workspace("CS-2047").model_copy(
        update={
            "case": _workspace("CS-2047").case.model_copy(update={"status": CaseStatus.COMPLETED})
        }
    )
    resolver = _EvidenceResolver(_evidence(EvidenceRetrievalStatus.RELEVANT))
    service = DecisionBriefService(
        _BriefStore(),
        _CaseStore(workspace),
        resolver,
        DeterministicDecisionEngine(),
        _GenerationStore(),
    )

    with pytest.raises(ProposalGenerationNotAllowed):
        service.generate(
            actor=DeterministicAuthProvider().authenticate("USR-0001"),
            case_id=workspace.case.public_id,
            expected_case_version=1,
            correlation_id="corr-test",
        )
    with pytest.raises(PermissionDenied):
        service.generate(
            actor=DeterministicAuthProvider().authenticate("USR-0004"),
            case_id=workspace.case.public_id,
            expected_case_version=1,
            correlation_id="corr-test",
        )
