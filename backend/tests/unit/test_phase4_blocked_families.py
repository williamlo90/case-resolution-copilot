"""A blocked reviewed change must explain the source defect before routing."""

from datetime import UTC, datetime

import pytest

from app.analysis.deterministic_decision_engine import DeterministicDecisionEngine
from app.domain.cases import CaseCategory, SourceFreshness
from app.domain.policies import EvidenceRetrievalStatus
from app.evaluation.decision_brief_fixtures import (
    build_evaluation_evidence,
    build_evaluation_workspace,
)


@pytest.mark.parametrize(
    ("facts", "policy_status", "expected"),
    [
        ({"secondary_record": "contradicts_primary"}, "relevant", "Resolved record conflict"),
        ({"supporting_record": "absent"}, "relevant", "Verified supporting record"),
        ({"approval_expired_at": "2026-10-12T23:00:00Z"}, "relevant", "Fresh approval"),
        ({"requesting_role": "specialist"}, "relevant", "Authorized reviewer"),
        ({}, "stale", "Current policy"),
        ({}, "conflicting", "Policy precedence"),
    ],
)
def test_source_defect_blocks_instead_of_preparing_an_effect(
    facts: dict[str, str], policy_status: str, expected: str
) -> None:
    workspace = build_evaluation_workspace("CS-2047")
    workspace.case.category = CaseCategory.REFUND_REQUEST
    workspace.case.source_freshness = SourceFreshness.CURRENT
    workspace.business_contexts = workspace.business_contexts[:1]
    workspace.business_contexts[0].source_freshness = SourceFreshness.CURRENT
    workspace.business_contexts[0].fields = {
        "requested_target": "SYNTHETIC-OBJECT-1",
        "original_recipient": "SYNTHETIC-OWNER-1",
        **facts,
    }
    status = EvidenceRetrievalStatus(policy_status)
    evidence = build_evaluation_evidence(workspace, status)
    result = DeterministicDecisionEngine().analyze(
        workspace=workspace, evidence=evidence, input_fingerprint="4" * 64
    )
    assert expected in [gap.label for gap in result.missing_information]
    assert result.state.value == "information_needed"
    assert not any(action.review_required for action in result.proposed_actions)


def test_expiry_is_compared_to_actual_aware_time() -> None:
    workspace = build_evaluation_workspace("CS-2047")
    workspace.case.source_freshness = SourceFreshness.CURRENT
    workspace.business_contexts = workspace.business_contexts[:1]
    workspace.business_contexts[0].source_freshness = SourceFreshness.CURRENT
    workspace.business_contexts[0].fields = {
        "requested_target": "SYNTHETIC-OBJECT-1",
        "approval_expired_at": datetime(2026, 10, 12, 23, tzinfo=UTC).isoformat(),
    }
    evidence = build_evaluation_evidence(workspace, EvidenceRetrievalStatus.RELEVANT)
    result = DeterministicDecisionEngine().analyze(
        workspace=workspace, evidence=evidence, input_fingerprint="4" * 64
    )
    assert any(gap.label == "Fresh approval" for gap in result.missing_information)
