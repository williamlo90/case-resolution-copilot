from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from httpx import Request
from openai import APITimeoutError

from app.analysis.ai_assisted_decision_engine import OpenAIAssistedDecisionEngine
from app.analysis.deterministic_decision_engine import DecisionEngine
from app.domain.cases import CaseWorkspaceRecord
from app.domain.decision_briefs import (
    AnalysisCheckpointDraft,
    AnalysisStatus,
    CheckpointStatus,
    DecisionAnalysis,
    DecisionProposalState,
    DecisionRiskCheck,
    ProposalConfidence,
    ProposedActionDraft,
    ResponseSuggestionStatus,
    RiskOutcome,
    SuggestedResponseDraft,
    VerifiedFact,
)
from app.domain.policies import EvidenceRetrievalResult, EvidenceRetrievalStatus
from app.models.gateway import ModelGatewayTimeout, ModelGatewayUnavailable
from app.models.openai_decision import (
    DecisionNarrative,
    OpenAIDecisionNarrativeGateway,
)
from app.persistence.decision_brief_helpers import decision_brief_audit_details
from tests.builders import valid_case_workspace, valid_evidence_result


def _baseline() -> DecisionAnalysis:
    now = datetime(2026, 7, 28, tzinfo=UTC)
    return DecisionAnalysis(
        status=AnalysisStatus.COMPLETED,
        policy_status=EvidenceRetrievalStatus.RELEVANT,
        facts=[
            VerifiedFact(
                id="FCT-1",
                statement="Payment status is recorded as settled.",
                source="Billing source",
                verified_at=now,
            )
        ],
        missing_information=[],
        risks=[
            DecisionRiskCheck(
                id="RSK-1",
                label="Human authority",
                outcome=RiskOutcome.REQUIRES_REVIEW,
                explanation="A reviewer must approve the financial action.",
            )
        ],
        outcome="Reverse the verified duplicate charge",
        impact_amount=Decimal("25.00"),
        impact_currency="USD",
        confidence=ProposalConfidence.MEDIUM,
        uncertainty="Human review is still required.",
        rationale="Verified records and policy support the proposed outcome.",
        state=DecisionProposalState.READY_FOR_REVIEW,
        proposed_actions=[
            ProposedActionDraft(
                type="reverse_duplicate_charge",
                label="Reverse the duplicate charge",
                parameters={
                    "case_id": "CS-SECRET",
                    "external_reference": "PRIVATE-REFERENCE",
                },
                impact_amount=Decimal("25.00"),
                impact_currency="USD",
                expected_outcome="The duplicate charge is reversed after approval.",
                review_required=True,
            )
        ],
        response_draft=SuggestedResponseDraft(
            subject="Proposed resolution",
            body="A resolution is ready for review.",
            status=ResponseSuggestionStatus.READY,
        ),
        checkpoints=[
            AnalysisCheckpointDraft(
                sequence=1,
                step="decision_brief",
                status=CheckpointStatus.COMPLETED,
                summary="Deterministic controls completed.",
                input_fingerprint="a" * 64,
                output_fingerprint="b" * 64,
            )
        ],
        risk_rule_version="generic-risk-rules-v1",
        model_version="deterministic-decision-engine-v1",
        prompt_version="decision-brief-rules-v1",
        graph_version="generic-decision-brief-v1",
    )


class _ParsedResponse:
    def __init__(self, output: DecisionNarrative | None) -> None:
        self.output_parsed = output


class _ResponsesResource:
    def __init__(
        self,
        output: DecisionNarrative | None = None,
        error: Exception | None = None,
    ) -> None:
        self.output = output
        self.error = error
        self.arguments: dict[str, Any] | None = None

    def parse(self, **kwargs: Any) -> _ParsedResponse:
        self.arguments = kwargs
        if self.error is not None:
            raise self.error
        return _ParsedResponse(self.output)


class _OpenAIClient:
    def __init__(self, responses: _ResponsesResource) -> None:
        self.responses = responses
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _narrative() -> DecisionNarrative:
    return DecisionNarrative(
        rationale="The verified payment record supports the proposed correction.",
        uncertainty="A reviewer must still approve the financial action.",
        response_subject="Update on your billing case",
        response_body=(
            "We verified the duplicate charge and prepared a correction for review. "
            "No account change will be made before approval."
        ),
    )


def test_openai_gateway_uses_structured_responses_with_minimized_context() -> None:
    resource = _ResponsesResource(output=_narrative())
    client = _OpenAIClient(resource)
    gateway = OpenAIDecisionNarrativeGateway(
        api_key="unused-test-key",
        model="gpt-5.6-luna",
        timeout_seconds=12,
        max_retries=1,
        client=client,
    )

    result = gateway.refine(_baseline())

    assert result == _narrative()
    assert resource.arguments is not None
    assert resource.arguments["model"] == "gpt-5.6-luna"
    assert resource.arguments["text_format"] is DecisionNarrative
    assert resource.arguments["store"] is False
    serialized_input = str(resource.arguments["input"])
    assert "Payment status is recorded as settled." in serialized_input
    assert "CS-SECRET" not in serialized_input
    assert "PRIVATE-REFERENCE" not in serialized_input

    gateway.close()
    assert client.closed is True


def test_openai_gateway_maps_timeout_without_leaking_provider_details() -> None:
    timeout = APITimeoutError(
        request=Request("POST", "https://api.openai.com/v1/responses")
    )
    gateway = OpenAIDecisionNarrativeGateway(
        api_key="unused-test-key",
        model="gpt-5.6-luna",
        timeout_seconds=12,
        max_retries=1,
        client=_OpenAIClient(_ResponsesResource(error=timeout)),
    )

    with pytest.raises(ModelGatewayTimeout, match="timed out"):
        gateway.refine(_baseline())


def test_openai_gateway_rejects_a_missing_structured_result() -> None:
    gateway = OpenAIDecisionNarrativeGateway(
        api_key="unused-test-key",
        model="gpt-5.6-luna",
        timeout_seconds=12,
        max_retries=1,
        client=_OpenAIClient(_ResponsesResource()),
    )

    with pytest.raises(ModelGatewayUnavailable, match="structured result"):
        gateway.refine(_baseline())


def test_openai_client_is_initialized_only_on_first_ai_request() -> None:
    resource = _ResponsesResource(output=_narrative())
    client = _OpenAIClient(resource)
    factory_calls = 0

    def client_factory() -> _OpenAIClient:
        nonlocal factory_calls
        factory_calls += 1
        return client

    gateway = OpenAIDecisionNarrativeGateway(
        api_key="unused-test-key",
        model="gpt-5.6-luna",
        timeout_seconds=12,
        max_retries=1,
        client_factory=client_factory,
    )

    assert factory_calls == 0
    gateway.refine(_baseline())
    gateway.refine(_baseline())
    assert factory_calls == 1


class _BaselineEngine:
    model_version = "deterministic-decision-engine-v1"
    prompt_version = "decision-brief-rules-v1"
    graph_version = "generic-decision-brief-v1"
    risk_rule_version = "generic-risk-rules-v1"

    def __init__(self, result: DecisionAnalysis) -> None:
        self.result = result

    def analyze(
        self,
        *,
        workspace: CaseWorkspaceRecord,
        evidence: EvidenceRetrievalResult,
        input_fingerprint: str,
    ) -> DecisionAnalysis:
        del workspace, evidence, input_fingerprint
        return self.result


class _NarrativeGateway:
    provider_name = "openai"
    model_version = "gpt-5.6-luna"

    def __init__(
        self,
        result: DecisionNarrative | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    def refine(self, analysis: DecisionAnalysis) -> DecisionNarrative:
        del analysis
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _run(engine: OpenAIAssistedDecisionEngine) -> DecisionAnalysis:
    return engine.analyze(
        workspace=valid_case_workspace(),
        evidence=valid_evidence_result(),
        input_fingerprint="f" * 64,
    )


def test_ai_assistance_changes_narrative_but_not_decision_controls() -> None:
    baseline = _baseline()
    engine = OpenAIAssistedDecisionEngine(
        baseline=cast(DecisionEngine, _BaselineEngine(baseline)),
        narrative_gateway=_NarrativeGateway(result=_narrative()),
    )

    result = _run(engine)

    assert result.rationale == _narrative().rationale
    assert result.response_draft.body == _narrative().response_body
    assert result.facts == baseline.facts
    assert result.missing_information == baseline.missing_information
    assert result.risks == baseline.risks
    assert result.outcome == baseline.outcome
    assert result.proposed_actions == baseline.proposed_actions
    assert result.state == baseline.state
    assert result.checkpoints[-1].step == "ai_narrative"
    assert result.checkpoints[-1].status is CheckpointStatus.COMPLETED
    assert result.model_version == "openai:gpt-5.6-luna"
    assert decision_brief_audit_details(result) == (
        "Decision brief prepared with AI-assisted wording.",
        "ai_assisted",
    )


def test_ai_assistance_falls_back_to_audited_deterministic_narrative() -> None:
    baseline = _baseline()
    engine = OpenAIAssistedDecisionEngine(
        baseline=cast(DecisionEngine, _BaselineEngine(baseline)),
        narrative_gateway=_NarrativeGateway(
            error=ModelGatewayUnavailable("provider unavailable")
        ),
    )

    result = _run(engine)

    assert result.rationale == baseline.rationale
    assert result.response_draft == baseline.response_draft
    assert result.proposed_actions == baseline.proposed_actions
    assert result.checkpoints[-1].step == "ai_narrative"
    assert result.checkpoints[-1].status is CheckpointStatus.ABSTAINED
    assert "provider" not in result.checkpoints[-1].summary.lower()
    assert result.model_version == "openai:gpt-5.6-luna:fallback"
    assert decision_brief_audit_details(result) == (
        "Decision brief prepared with the built-in backup draft.",
        "verified_fallback",
    )


def test_ai_draft_cannot_claim_a_controlled_action_already_happened() -> None:
    baseline = _baseline()
    unsafe = _narrative().model_copy(
        update={"response_body": "We have issued the refund to your account."}
    )
    engine = OpenAIAssistedDecisionEngine(
        baseline=cast(DecisionEngine, _BaselineEngine(baseline)),
        narrative_gateway=_NarrativeGateway(result=unsafe),
    )

    result = _run(engine)

    assert result.response_draft == baseline.response_draft
    assert result.rationale == baseline.rationale
    assert result.checkpoints[-1].status is CheckpointStatus.ABSTAINED
    assert result.model_version == "openai:gpt-5.6-luna:rejected"
