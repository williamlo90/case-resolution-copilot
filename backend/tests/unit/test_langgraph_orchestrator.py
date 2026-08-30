from app.analysis.deterministic_decision_engine import DeterministicDecisionEngine
from app.domain.cases import CaseWorkspaceRecord
from app.domain.decision_briefs import DecisionAnalysis
from app.domain.policies import EvidenceRetrievalResult
from app.evaluation.decision_brief_fixtures import (
    decision_brief_expectations,
    prepare_evaluation_input,
)
from app.orchestrators.langgraph_orchestrator import LangGraphDecisionOrchestrator


def test_langgraph_is_a_real_production_boundary_over_governed_controls() -> None:
    baseline = DeterministicDecisionEngine()
    orchestrator = LangGraphDecisionOrchestrator(baseline)
    expectation, workspace, evidence, fingerprint = prepare_evaluation_input(
        expectation=decision_brief_expectations()[0],
        engine=orchestrator,
    )

    result = orchestrator.analyze(
        workspace=workspace,
        evidence=evidence,
        input_fingerprint=fingerprint,
    )

    assert result.status is expectation.analysis_status
    assert result.state is expectation.proposal_state
    assert result.checkpoints[0].input_fingerprint == fingerprint
    assert result.graph_version == orchestrator.graph_version
    assert orchestrator.descriptor.default_runtime is True
    assert orchestrator.descriptor.framework == "LangGraph"


class _BrokenCheckpointEngine(DeterministicDecisionEngine):
    def analyze(
        self,
        *,
        workspace: CaseWorkspaceRecord,
        evidence: EvidenceRetrievalResult,
        input_fingerprint: str,
    ) -> DecisionAnalysis:
        result = super().analyze(
            workspace=workspace,
            evidence=evidence,
            input_fingerprint=input_fingerprint,
        )
        broken = result.checkpoints[1].model_copy(update={"input_fingerprint": "0" * 64})
        return result.model_copy(
            update={"checkpoints": [result.checkpoints[0], broken, *result.checkpoints[2:]]}
        )


def test_langgraph_fails_closed_when_checkpoint_lineage_is_broken() -> None:
    orchestrator = LangGraphDecisionOrchestrator(_BrokenCheckpointEngine())
    _, workspace, evidence, fingerprint = prepare_evaluation_input(
        expectation=decision_brief_expectations()[0],
        engine=orchestrator,
    )

    try:
        orchestrator.analyze(
            workspace=workspace,
            evidence=evidence,
            input_fingerprint=fingerprint,
        )
    except RuntimeError as error:
        assert "lineage" in str(error)
    else:
        raise AssertionError("A broken checkpoint chain must be rejected.")
