from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from httpx import Request
from openai import APITimeoutError
from pydantic import ValidationError

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
    InformationGap,
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
    OPENAI_DECISION_MAX_INPUT_CHARS,
    OPENAI_DECISION_MAX_OUTPUT_TOKENS,
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
        model_version="deterministic-decision-engine-v2",
        prompt_version="decision-brief-rules-v2",
        graph_version="generic-decision-brief-v1",
    )


def _information_needed_baseline() -> DecisionAnalysis:
    baseline = _baseline()
    return baseline.model_copy(
        update={
            "missing_information": [
                InformationGap(
                    id="GAP-1",
                    label="Second payment reference",
                    description=(
                        "Confirm a second settled payment reference before treating the "
                        "charge as a duplicate."
                    ),
                    blocking=True,
                )
            ],
            "outcome": "Verify the second charge before a billing adjustment",
            "impact_amount": None,
            "impact_currency": None,
            "confidence": ProposalConfidence.LOW,
            "uncertainty": (
                "The outcome remains uncertain until the second payment reference is confirmed."
            ),
            "state": DecisionProposalState.INFORMATION_NEEDED,
            "proposed_actions": [
                ProposedActionDraft(
                    type="request_information",
                    label="Request the missing information",
                    parameters={"items": "Second payment reference"},
                    impact_amount=None,
                    impact_currency=None,
                    expected_outcome=(
                        "Blocking information is recorded before the decision is revised."
                    ),
                    review_required=False,
                )
            ],
            "response_draft": SuggestedResponseDraft(
                subject="Information needed for your billing case",
                body=(
                    "Hello Dimas Setiawan,\n\nOur records currently show one captured "
                    "payment record, not two settled charges.\n\nPlease send the second "
                    "settled payment reference or an updated statement showing both charges."
                ),
                status=ResponseSuggestionStatus.BLOCKED,
            ),
        }
    )


class _ParsedResponse:
    def __init__(
        self,
        output: DecisionNarrative | None,
        usage: "_Usage | None" = None,
    ) -> None:
        self.output_parsed = output
        self.usage = usage


class _InputTokenDetails:
    def __init__(self, *, cached_tokens: int, cache_write_tokens: int) -> None:
        self.cached_tokens = cached_tokens
        self.cache_write_tokens = cache_write_tokens


class _OutputTokenDetails:
    def __init__(self, *, reasoning_tokens: int) -> None:
        self.reasoning_tokens = reasoning_tokens


class _Usage:
    def __init__(
        self,
        *,
        input_tokens: int,
        cached_tokens: int,
        cache_write_tokens: int,
        output_tokens: int,
        reasoning_tokens: int,
    ) -> None:
        self.input_tokens = input_tokens
        self.input_tokens_details = _InputTokenDetails(
            cached_tokens=cached_tokens,
            cache_write_tokens=cache_write_tokens,
        )
        self.output_tokens = output_tokens
        self.output_tokens_details = _OutputTokenDetails(reasoning_tokens=reasoning_tokens)
        self.total_tokens = input_tokens + output_tokens


class _ResponsesResource:
    def __init__(
        self,
        output: DecisionNarrative | None = None,
        error: Exception | None = None,
        usage: _Usage | None = None,
    ) -> None:
        self.output = output
        self.error = error
        self.usage = usage
        self.arguments: dict[str, Any] | None = None

    def parse(self, **kwargs: Any) -> _ParsedResponse:
        self.arguments = kwargs
        if self.error is not None:
            raise self.error
        return _ParsedResponse(self.output, self.usage)


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
    resource = _ResponsesResource(
        output=_narrative(),
        usage=_Usage(
            input_tokens=100,
            cached_tokens=20,
            cache_write_tokens=10,
            output_tokens=40,
            reasoning_tokens=8,
        ),
    )
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
    assert resource.arguments["max_output_tokens"] == OPENAI_DECISION_MAX_OUTPUT_TOKENS
    serialized_input = str(resource.arguments["input"])
    assert len(serialized_input) <= OPENAI_DECISION_MAX_INPUT_CHARS
    assert "ready_for_review" in serialized_input
    assert "Payment status is recorded as settled." in serialized_input
    assert "CS-SECRET" not in serialized_input
    assert "PRIVATE-REFERENCE" not in serialized_input
    assert len(gateway.usage_records) == 1
    assert gateway.usage_records[0].input_tokens == 100
    assert gateway.usage_records[0].cached_input_tokens == 20
    assert gateway.usage_records[0].cache_write_input_tokens == 10
    assert gateway.usage_records[0].output_tokens == 40
    assert gateway.usage_records[0].reasoning_output_tokens == 8
    assert gateway.usage_records[0].total_tokens == 140

    gateway.close()
    assert client.closed is True


def test_openai_gateway_maps_timeout_without_leaking_provider_details() -> None:
    timeout = APITimeoutError(request=Request("POST", "https://api.openai.com/v1/responses"))
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


def test_openai_gateway_maps_invalid_structured_output_to_safe_failure() -> None:
    try:
        DecisionNarrative.model_validate({"rationale": "Incomplete output"})
    except ValidationError as validation_error:
        error = validation_error
    else:  # pragma: no cover - protects the test fixture from a weakened schema
        raise AssertionError("The incomplete narrative fixture unexpectedly validated.")
    gateway = OpenAIDecisionNarrativeGateway(
        api_key="unused-test-key",
        model="gpt-5.6-luna",
        timeout_seconds=12,
        max_retries=1,
        client=_OpenAIClient(_ResponsesResource(error=error)),
    )

    with pytest.raises(ModelGatewayUnavailable, match="invalid structured result"):
        gateway.refine(_baseline())


def test_openai_gateway_rejects_oversized_input_before_provider_access() -> None:
    resource = _ResponsesResource(output=_narrative())
    baseline = _baseline()
    source_fact = baseline.facts[0]
    oversized = baseline.model_copy(
        update={
            "facts": [
                source_fact.model_copy(
                    update={
                        "id": f"FCT-LARGE-{index}",
                        "statement": "x" * 1000,
                    }
                )
                for index in range(30)
            ]
        }
    )
    gateway = OpenAIDecisionNarrativeGateway(
        api_key="unused-test-key",
        model="gpt-5.6-luna",
        timeout_seconds=12,
        max_retries=1,
        client=_OpenAIClient(resource),
    )

    with pytest.raises(ModelGatewayUnavailable, match="safety limit"):
        gateway.refine(oversized)

    assert resource.arguments is None


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
    model_version = "deterministic-decision-engine-v2"
    prompt_version = "decision-brief-rules-v2"
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
        narrative_gateway=_NarrativeGateway(error=ModelGatewayUnavailable("provider unavailable")),
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


@pytest.mark.parametrize(
    ("field", "unsafe_claim"),
    [
        ("rationale", "We refunded the customer account."),
        ("uncertainty", "The credit has been applied."),
        ("response_subject", "Your refund has been processed"),
        ("response_body", "We've issued the refund to your account."),
    ],
)
def test_ai_narrative_cannot_claim_a_controlled_action_already_happened(
    field: str,
    unsafe_claim: str,
) -> None:
    baseline = _baseline()
    unsafe = _narrative().model_copy(update={field: unsafe_claim})
    engine = OpenAIAssistedDecisionEngine(
        baseline=cast(DecisionEngine, _BaselineEngine(baseline)),
        narrative_gateway=_NarrativeGateway(result=unsafe),
    )

    result = _run(engine)

    assert result.response_draft == baseline.response_draft
    assert result.rationale == baseline.rationale
    assert result.checkpoints[-1].status is CheckpointStatus.ABSTAINED
    assert result.model_version == "openai:gpt-5.6-luna:rejected"


def test_ai_narrative_allows_explicitly_pending_action_language() -> None:
    baseline = _baseline()
    pending = _narrative().model_copy(
        update={
            "response_body": (
                "We have not reversed the duplicate charge. The proposed reversal remains "
                "pending approval."
            )
        }
    )
    engine = OpenAIAssistedDecisionEngine(
        baseline=cast(DecisionEngine, _BaselineEngine(baseline)),
        narrative_gateway=_NarrativeGateway(result=pending),
    )

    result = _run(engine)

    assert result.response_draft.body == pending.response_body
    assert result.checkpoints[-1].status is CheckpointStatus.COMPLETED


def test_ai_narrative_rejects_a_generic_information_needed_response() -> None:
    baseline = _information_needed_baseline()
    generic = DecisionNarrative(
        rationale="A second settled payment reference is still required.",
        uncertainty="The duplicate charge cannot be confirmed yet.",
        response_subject="Update on your case",
        response_body="We received your request and are reviewing the available information.",
    )
    engine = OpenAIAssistedDecisionEngine(
        baseline=cast(DecisionEngine, _BaselineEngine(baseline)),
        narrative_gateway=_NarrativeGateway(result=generic),
    )

    result = _run(engine)

    assert result.response_draft == baseline.response_draft
    assert result.checkpoints[-1].status is CheckpointStatus.ABSTAINED
    assert result.model_version == "openai:gpt-5.6-luna:misaligned"


def test_ai_narrative_accepts_a_specific_information_request() -> None:
    baseline = _information_needed_baseline()
    specific = DecisionNarrative(
        rationale="A second settled payment reference is still required.",
        uncertainty="The duplicate charge cannot be confirmed yet.",
        response_subject="Information needed for your billing case",
        response_body=(
            "Please send the second settled payment reference or an updated statement "
            "showing both charges. We need it before considering a billing adjustment."
        ),
    )
    engine = OpenAIAssistedDecisionEngine(
        baseline=cast(DecisionEngine, _BaselineEngine(baseline)),
        narrative_gateway=_NarrativeGateway(result=specific),
    )

    result = _run(engine)

    assert result.response_draft.body == specific.response_body
    assert result.checkpoints[-1].status is CheckpointStatus.COMPLETED


def test_ai_narrative_rejects_internal_control_language_in_customer_draft() -> None:
    baseline = _baseline()
    internal = _narrative().model_copy(
        update={
            "response_body": (
                "The duplicate charge reversal has low confidence and needs supervisor approval."
            )
        }
    )
    engine = OpenAIAssistedDecisionEngine(
        baseline=cast(DecisionEngine, _BaselineEngine(baseline)),
        narrative_gateway=_NarrativeGateway(result=internal),
    )

    result = _run(engine)

    assert result.response_draft == baseline.response_draft
    assert result.model_version == "openai:gpt-5.6-luna:misaligned"
