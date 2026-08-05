from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.analysis.ai_assisted_decision_engine import OpenAIAssistedDecisionEngine
from app.analysis.deterministic_decision_engine import DeterministicDecisionEngine
from app.domain.decision_briefs import DecisionAnalysis
from app.evaluation.decision_brief_runtime import (
    BoundedNarrativeGateway,
    build_evaluation_evidence,
    build_evaluation_workspace,
    run_decision_brief_evaluation,
)
from app.models.gateway import ModelGatewayUnavailable
from app.models.openai_decision import DecisionNarrative

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


class _SuccessfulNarrativeGateway:
    provider_name = "openai"
    model_version = "evaluation-test-model"

    def __init__(self, contract_path: Path) -> None:
        self._contract_path = contract_path

    def refine(self, analysis: DecisionAnalysis) -> DecisionNarrative:
        assert self._contract_path.is_file()
        action_pending = any(action.review_required for action in analysis.proposed_actions)
        return DecisionNarrative(
            rationale="The verified records support the server-owned proposed outcome.",
            uncertainty="A human reviewer retains authority over consequential actions.",
            response_subject="Update on your support case",
            response_body=(
                "The proposed action is pending supervisor approval before any change is made."
                if action_pending
                else "We need the listed information before confirming an outcome."
            ),
        )


class _UnavailableNarrativeGateway:
    provider_name = "openai"
    model_version = "evaluation-test-model"

    def refine(self, analysis: DecisionAnalysis) -> DecisionNarrative:
        del analysis
        raise ModelGatewayUnavailable("provider unavailable")


def test_decision_brief_runtime_evaluation_freezes_controls_and_bounds_provider_calls(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "benchmark-data"
    run_id = "provider-success"
    contract_path = output_root / "runs" / "decision-brief" / run_id / "contract.json"
    bounded_gateway = BoundedNarrativeGateway(_SuccessfulNarrativeGateway(contract_path))
    engine = OpenAIAssistedDecisionEngine(
        baseline=DeterministicDecisionEngine(),
        narrative_gateway=bounded_gateway,
    )

    report = run_decision_brief_evaluation(
        engine=engine,
        output_root=output_root,
        execution_mode="provider",
        run_id=run_id,
        provider_counter=bounded_gateway,
        clock=lambda: NOW,
    )

    assert report.total == 3
    assert report.passed == 3
    assert report.safety_passed == 3
    assert report.provider_calls_expected == 2
    assert report.provider_calls == 2
    assert report.control_preservation_rate == 1
    assert [item.model_mode for item in report.cases] == [
        "ai_assisted",
        "ai_assisted",
        "skipped",
    ]
    assert all(item.controls_preserved for item in report.cases)
    assert all(item.provider_call_match for item in report.cases)
    assert contract_path.is_file()
    assert contract_path.with_name("progress.json").is_file()
    report_path = contract_path.with_name("report.json")
    assert report_path.is_file()
    assert "pending supervisor approval" not in report_path.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        run_decision_brief_evaluation(
            engine=engine,
            output_root=output_root,
            execution_mode="provider",
            run_id=run_id,
            provider_counter=bounded_gateway,
            clock=lambda: NOW,
        )
    assert bounded_gateway.calls == 2

    workspace = build_evaluation_workspace("CS-2047")
    evidence = build_evaluation_evidence(workspace, report.cases[1].policy_status)
    baseline = DeterministicDecisionEngine().analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint="f" * 64,
    )
    with pytest.raises(RuntimeError, match="call ceiling"):
        bounded_gateway.refine(baseline)


def test_decision_brief_runtime_evaluation_records_safe_provider_fallback(
    tmp_path: Path,
) -> None:
    bounded_gateway = BoundedNarrativeGateway(_UnavailableNarrativeGateway())
    engine = OpenAIAssistedDecisionEngine(
        baseline=DeterministicDecisionEngine(),
        narrative_gateway=bounded_gateway,
    )

    report = run_decision_brief_evaluation(
        engine=engine,
        output_root=tmp_path / "benchmark-data",
        execution_mode="provider",
        run_id="provider-fallback",
        provider_counter=bounded_gateway,
        clock=lambda: NOW,
    )

    assert report.provider_calls == 2
    assert report.safe_fallback == 2
    assert report.skipped == 1
    assert report.safety_passed == 3
    assert report.passed == 1
    assert report.failed == 2
    assert all(item.controls_preserved for item in report.cases)
    assert [item.model_mode_match for item in report.cases] == [False, False, True]


def test_decision_brief_runtime_evaluation_rejects_unsafe_run_ids(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "benchmark-data"

    with pytest.raises(ValueError, match="run ID"):
        run_decision_brief_evaluation(
            engine=DeterministicDecisionEngine(),
            output_root=output_root,
            execution_mode="deterministic",
            run_id="../../outside",
            clock=lambda: NOW,
        )

    assert not output_root.exists()
