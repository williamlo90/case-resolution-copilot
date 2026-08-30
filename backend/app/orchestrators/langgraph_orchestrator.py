from typing import NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.analysis.deterministic_decision_engine import DecisionEngine
from app.domain.cases import CaseWorkspaceRecord
from app.domain.decision_briefs import DecisionAnalysis
from app.domain.policies import EvidenceRetrievalResult
from app.orchestrators.base import OrchestratorDescriptor


class DecisionGraphState(TypedDict):
    workspace: CaseWorkspaceRecord
    evidence: EvidenceRetrievalResult
    input_fingerprint: str
    analysis: NotRequired[DecisionAnalysis]


class LangGraphDecisionOrchestrator:
    """Thin production graph around server-owned decision controls."""

    descriptor = OrchestratorDescriptor(
        name="case-decision-v1",
        framework="LangGraph",
        kind="production",
        default_runtime=True,
        purpose="Execute and verify the governed decision-analysis checkpoint chain.",
    )

    def __init__(self, delegate: DecisionEngine) -> None:
        self.delegate = delegate
        self.model_version = delegate.model_version
        self.prompt_version = delegate.prompt_version
        self.graph_version = f"langgraph-case-decision-v1:{delegate.graph_version}"
        self.risk_rule_version = delegate.risk_rule_version
        self._graph = self._compile_graph()

    def analyze(
        self,
        *,
        workspace: CaseWorkspaceRecord,
        evidence: EvidenceRetrievalResult,
        input_fingerprint: str,
    ) -> DecisionAnalysis:
        result = cast(
            DecisionGraphState,
            self._graph.invoke(
                DecisionGraphState(
                    workspace=workspace,
                    evidence=evidence,
                    input_fingerprint=input_fingerprint,
                )
            ),
        )
        analysis = result.get("analysis")
        if analysis is None:
            raise RuntimeError("The LangGraph decision workflow produced no analysis.")
        return analysis

    def _compile_graph(
        self,
    ) -> CompiledStateGraph[DecisionGraphState, None, DecisionGraphState, DecisionGraphState]:
        graph = StateGraph(DecisionGraphState)
        graph.add_node("governed_analysis", self._run_governed_analysis)
        graph.add_node("verify_checkpoint_chain", self._verify_checkpoint_chain)
        graph.add_edge(START, "governed_analysis")
        graph.add_edge("governed_analysis", "verify_checkpoint_chain")
        graph.add_edge("verify_checkpoint_chain", END)
        return graph.compile()

    def _run_governed_analysis(self, state: DecisionGraphState) -> DecisionGraphState:
        analysis = self.delegate.analyze(
            workspace=state["workspace"],
            evidence=state["evidence"],
            input_fingerprint=state["input_fingerprint"],
        )
        return {**state, "analysis": analysis}

    def _verify_checkpoint_chain(self, state: DecisionGraphState) -> DecisionGraphState:
        analysis = state.get("analysis")
        if analysis is None:
            raise RuntimeError("The governed analysis node returned no decision.")
        previous_fingerprint = state["input_fingerprint"]
        for expected_sequence, checkpoint in enumerate(analysis.checkpoints, start=1):
            if checkpoint.sequence != expected_sequence:
                raise RuntimeError("Decision checkpoints are not sequential.")
            if checkpoint.input_fingerprint != previous_fingerprint:
                raise RuntimeError("Decision checkpoint lineage is not continuous.")
            previous_fingerprint = checkpoint.output_fingerprint
        return {
            **state,
            "analysis": analysis.model_copy(update={"graph_version": self.graph_version}),
        }
