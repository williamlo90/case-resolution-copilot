from typing import cast

import pytest

from app.domain.cases import CaseStatus, CaseWorkspaceRecord
from app.domain.decision_briefs import (
    DecisionBriefRecord,
    DecisionProposalState,
    ResponseSuggestionStatus,
)
from app.domain.policies import (
    EvidenceRetrievalResult,
    EvidenceRetrievalStatus,
    PolicyEvidenceBundle,
)
from app.domain.reviews import (
    ReviewPolicyState,
    ReviewSnapshotStale,
    ReviewSubmission,
    ReviewSubmissionNotAllowed,
)
from app.security.authentication import DeterministicAuthProvider
from app.security.authorization import PermissionDenied
from app.services import review_service
from app.services.review_service import (
    ReviewCaseStore,
    ReviewDecisionStore,
    ReviewEvidenceResolver,
    ReviewPolicyStore,
    ReviewService,
    ReviewStore,
)
from tests.builders import (
    valid_case_workspace,
    valid_decision_brief,
    valid_evidence_result,
)


class _StopAfterSubmit(RuntimeError):
    pass


def _brief(
    *,
    policy_status: EvidenceRetrievalStatus = EvidenceRetrievalStatus.RELEVANT,
    state: DecisionProposalState = DecisionProposalState.READY_FOR_REVIEW,
    review_required: bool = True,
) -> DecisionBriefRecord:
    return valid_decision_brief(
        policy_status=policy_status,
        state=state,
        response_status=(
            ResponseSuggestionStatus.READY
            if state is DecisionProposalState.READY_FOR_REVIEW
            else ResponseSuggestionStatus.BLOCKED
        ),
        review_required=review_required,
        input_fingerprint="a" * 64,
        context_fingerprint="b" * 64,
        evidence_fingerprint="c" * 64,
        risk_fingerprint="d" * 64,
    )


class _RecordingStore:
    def __init__(self) -> None:
        self.command: ReviewSubmission | None = None
        self.reads = 0

    def get_for_proposal(self, **values: object) -> None:
        del values
        self.reads += 1
        return None

    def submit(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        command: ReviewSubmission,
        correlation_id: str,
    ) -> None:
        del organization_public_id, case_public_id, actor_id, correlation_id
        self.command = command
        raise _StopAfterSubmit


class _CaseStore:
    def __init__(
        self,
        status: CaseStatus = CaseStatus.INVESTIGATING,
    ) -> None:
        case_id = {
            CaseStatus.NEW: "CS-2048",
            CaseStatus.INVESTIGATING: "CS-2047",
            CaseStatus.INFORMATION_NEEDED: "CS-2046",
        }[status]
        self.workspace = valid_case_workspace(case_id)

    def get_workspace(self, **values: object) -> CaseWorkspaceRecord:
        del values
        return self.workspace


class _DecisionStore:
    def __init__(self, brief: DecisionBriefRecord) -> None:
        self.brief = brief

    def get_version(self, **values: object) -> DecisionBriefRecord:
        del values
        return self.brief


class _PolicyStore:
    def list_evidence_for_case(self, **values: object) -> list[PolicyEvidenceBundle]:
        del values
        return []


class _EvidenceResolver:
    def __init__(self, status: EvidenceRetrievalStatus) -> None:
        self.result = valid_evidence_result(status)

    def refresh_for_case(self, **values: object) -> EvidenceRetrievalResult:
        del values
        return self.result


def _service(
    store: _RecordingStore,
    brief: DecisionBriefRecord,
    status: EvidenceRetrievalStatus,
    case_status: CaseStatus = CaseStatus.INVESTIGATING,
) -> ReviewService:
    return ReviewService(
        cast(ReviewStore, store),
        cast(ReviewCaseStore, _CaseStore(case_status)),
        cast(ReviewDecisionStore, _DecisionStore(brief)),
        cast(ReviewPolicyStore, _PolicyStore()),
        cast(ReviewEvidenceResolver, _EvidenceResolver(status)),
    )


def _fixed_fingerprints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        review_service,
        "combined_context_fingerprint",
        lambda workspace: "b" * 64,
    )
    monkeypatch.setattr(
        review_service,
        "combined_evidence_fingerprint",
        lambda evidence: "c" * 64,
    )


def test_submit_builds_server_owned_executable_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_fingerprints(monkeypatch)
    store = _RecordingStore()
    service = _service(store, _brief(), EvidenceRetrievalStatus.RELEVANT)
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(_StopAfterSubmit):
        service.submit(
            actor=actor,
            case_id="CS-TEST",
            proposal_version=1,
            expected_case_version=1,
            correlation_id="corr-test",
        )

    assert store.command is not None
    assert store.command.policy_state is ReviewPolicyState.SUPPORTED
    assert store.command.execution_eligible
    assert store.command.approval_rule.required_role.value == "supervisor"
    assert store.command.expected_case_version == 1
    assert len(store.command.snapshot_fingerprint) == 64


def test_submit_allows_governed_escalation_but_never_marks_it_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_fingerprints(monkeypatch)
    store = _RecordingStore()
    service = _service(
        store,
        _brief(
            policy_status=EvidenceRetrievalStatus.MISSING,
            state=DecisionProposalState.INFORMATION_NEEDED,
            review_required=False,
        ),
        EvidenceRetrievalStatus.MISSING,
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(_StopAfterSubmit):
        service.submit(
            actor=actor,
            case_id="CS-TEST",
            proposal_version=1,
            expected_case_version=1,
            correlation_id="corr-test",
        )

    assert store.command is not None
    assert store.command.policy_state is ReviewPolicyState.MISSING
    assert not store.command.execution_eligible


def test_submit_rejects_changed_context_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_fingerprints(monkeypatch)
    monkeypatch.setattr(
        review_service,
        "combined_context_fingerprint",
        lambda workspace: "f" * 64,
    )
    store = _RecordingStore()
    service = _service(store, _brief(), EvidenceRetrievalStatus.RELEVANT)
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(ReviewSnapshotStale, match="Business context changed"):
        service.submit(
            actor=actor,
            case_id="CS-TEST",
            proposal_version=1,
            expected_case_version=1,
            correlation_id="corr-test",
        )

    assert store.command is None


def test_auditor_cannot_submit_review_and_store_is_not_read() -> None:
    store = _RecordingStore()
    service = _service(store, _brief(), EvidenceRetrievalStatus.RELEVANT)
    actor = DeterministicAuthProvider().authenticate("USR-0004")

    with pytest.raises(PermissionDenied):
        service.submit(
            actor=actor,
            case_id="CS-TEST",
            proposal_version=1,
            expected_case_version=1,
            correlation_id="corr-test",
        )

    assert store.reads == 0


def test_review_submission_requires_an_active_investigation() -> None:
    store = _RecordingStore()
    service = _service(
        store,
        _brief(),
        EvidenceRetrievalStatus.RELEVANT,
        case_status=CaseStatus.INFORMATION_NEEDED,
    )
    actor = DeterministicAuthProvider().authenticate("USR-0001")

    with pytest.raises(
        ReviewSubmissionNotAllowed,
        match="Move this case into investigation",
    ):
        service.submit(
            actor=actor,
            case_id="CS-TEST",
            proposal_version=1,
            expected_case_version=1,
            correlation_id="corr-test",
        )

    assert store.command is None
