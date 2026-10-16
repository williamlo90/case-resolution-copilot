import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

import pytest

from app.analysis.deterministic_decision_engine import DeterministicDecisionEngine
from app.analysis.sop_rules import parse_rules, validate_rule_scope
from app.domain.decision_briefs import DecisionAnalysis
from app.domain.policies import EvidenceRetrievalStatus
from app.evaluation.decision_brief_fixtures import (
    build_evaluation_evidence,
    build_evaluation_workspace,
)
from app.evaluation.sop_replay import load_inputs, observe, retrieve


def test_refund_window_is_enforced_from_published_source() -> None:
    workspace = build_evaluation_workspace("CS-2047")
    workspace.business_contexts[0].fields["purchased_at"] = "2026-01-01T00:00:00Z"
    evidence = build_evaluation_evidence(workspace, EvidenceRetrievalStatus.RELEVANT)
    rule = {"schema_version": 1, "rules": [{"kind": "refund_window", "max_days": 7}]}
    for bundle in evidence.evidence:
        bundle.version.case_categories = ["refund_request"]
        bundle.version.source_text += "\n```case-resolution-rules\n" + json.dumps(rule) + "\n```"
        bundle.version.content_hash = sha256(bundle.version.source_text.encode()).hexdigest()
        bundle.evidence.policy_content_hash = bundle.version.content_hash
    result = DeterministicDecisionEngine().analyze(
        workspace=workspace, evidence=evidence, input_fingerprint="3" * 64
    )
    assert not any(action.type == "issue_refund" for action in result.proposed_actions)
    assert "refund_window" in " ".join(gap.description for gap in result.missing_information)


@pytest.mark.parametrize("family", ["refund", "ownership", "threshold"])
def test_new_revision_controls_real_decision_engine(family: str) -> None:
    data = load_inputs()
    case = next(c for c in data.cases if c.family == family and c.id.endswith("CHANGING"))
    at = datetime(2026, 10, 9, tzinfo=UTC)
    revision = retrieve(data, case, at)
    result = observe(case, revision, at)
    assert revision.version == 2
    assert result["analysis"]["state"] == (  # type: ignore[index]
        "ready_for_review" if family == "refund" else "information_needed"
    )
    if family != "refund":
        analysis = DecisionAnalysis.model_validate(result["analysis"])
        assert analysis.missing_information
        assert all(gap.label == "SOP review required" for gap in analysis.missing_information)


@pytest.mark.parametrize("family", ["refund", "ownership", "threshold"])
def test_unchanged_controls_remain_eligible_under_revised_sop(family: str) -> None:
    data = load_inputs()
    case = next(c for c in data.cases if c.family == family and c.id.endswith("CONTROL"))
    result = observe(case, retrieve(data, case, data.dates[1]), data.dates[1])
    assert result["analysis"]["state"] == "ready_for_review"  # type: ignore[index]
    assert not result["analysis"]["missing_information"]  # type: ignore[index]


@pytest.mark.parametrize(
    "at,version",
    [
        (datetime(2026, 10, 8, tzinfo=UTC) - timedelta(microseconds=1), 1),
        (datetime(2026, 10, 8, tzinfo=UTC), 2),
        (datetime(2026, 10, 12, tzinfo=UTC) - timedelta(microseconds=1), 2),
        (datetime(2026, 10, 12, tzinfo=UTC), 3),
    ],
)
def test_effective_intervals_are_start_inclusive_end_exclusive(at: datetime, version: int) -> None:
    data = load_inputs()
    assert retrieve(data, data.cases[0], at).version == version


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 2, "rules": []},
        {"schema_version": 1, "rules": [{"kind": "refund_window", "max_days": True}]},
        {"schema_version": 1, "rules": [{"kind": "refund_window", "max_days": -1}]},
        {"schema_version": 1, "rules": [{"kind": "refund_window", "max_days": "7"}]},
        {"schema_version": 1, "rules": [{"kind": "remote_code", "code": "ignored"}]},
        {"schema_version": 1, "rules": [{"kind": "refund_window", "max_days": 7}] * 2},
    ],
)
def test_malformed_or_ambiguous_rules_fail_closed(payload: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        parse_rules("```case-resolution-rules\n" + json.dumps(payload) + "\n```")


def test_wrong_category_cannot_publish_executable_rules() -> None:
    source = load_inputs().policies[0].source
    with pytest.raises(ValueError):
        validate_rule_scope(source, ["account_access"])


@pytest.mark.parametrize("delta,allowed", [(0, True), (1, False)])
def test_exact_refund_deadline_boundary(delta: int, allowed: bool) -> None:
    data = load_inputs()
    case = data.cases[0].model_copy(deep=True)
    purchased = case.workspace.request.received_at - timedelta(days=7, microseconds=delta)
    for context in case.workspace.business_contexts:
        context.fields["purchased_at"] = purchased.isoformat()
    result = observe(case, data.policies[0], data.dates[0])
    assert (result["analysis"]["state"] == "ready_for_review") == allowed  # type: ignore[index]


def test_invalid_rule_does_not_fall_back_to_legacy_refund() -> None:
    data = load_inputs()
    revision = data.policies[0].model_copy(update={"source": "```case-resolution-rules\n{}\n```"})
    result = observe(data.cases[0], revision, data.dates[0])
    assert result["analysis"]["state"] == "information_needed"  # type: ignore[index]


def test_stronger_ownership_proof_never_overrides_conflicting_records() -> None:
    data = load_inputs()
    case = next(c for c in data.cases if c.id == "REPLAY-OWNERSHIP-CONTROL").model_copy(deep=True)
    case.workspace.business_contexts[0].fields["ownership_match"] = "conflicting"
    at = data.dates[1]
    result = observe(case, retrieve(data, case, at), at)
    assert result["analysis"]["state"] == "information_needed"  # type: ignore[index]


@pytest.mark.parametrize("purchased", ["", "2026-09-20", "2027-01-01T00:00:00Z"])
def test_missing_naive_or_future_purchase_cannot_authorize_refund(purchased: str) -> None:
    data = load_inputs()
    case = data.cases[0].model_copy(deep=True)
    for context in case.workspace.business_contexts:
        context.fields["purchased_at"] = purchased
    result = observe(case, data.policies[0], data.dates[0])
    assert result["analysis"]["state"] == "information_needed"  # type: ignore[index]
