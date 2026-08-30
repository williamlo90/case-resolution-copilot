from collections.abc import Callable
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.decision_briefs import DecisionAnalysis
from app.models.gateway import ModelGatewayTimeout, ModelGatewayUnavailable
from app.models.provider_usage import ProviderTokenUsage
from app.orchestrators.langchain_helpers import (
    DecisionNarrativePromptTooLarge,
    build_decision_narrative_messages,
)

OPENAI_DECISION_INSTRUCTIONS = """
Draft clear support decision language from the supplied server-generated control record.
Use plain business language and short sentences.

The server-owned facts, policy status, risk checks, proposed outcome, financial impact,
actions, and approval requirements are authoritative. Do not add, remove, or change them.
Do not invent customer details, policy clauses, evidence, amounts, or completed actions.
Never claim that an action has already happened. Make the response draft clear that any
review-required action remains pending human approval.

The response draft is customer-facing and must follow the proposal state and next safe action.
When information is needed, name the exact missing record, ask for it in practical language,
explain why it is needed, and say what happens next. Do not replace a known information gap with
a generic acknowledgement such as "we are reviewing your request." When a resolution is ready
for review, mention the verified basis in plain language, describe the proposed action as pending,
and state that it has not happened yet.

Do not expose internal IDs, policy versions, confidence labels, risk-check names, approval roles,
or implementation terms in the customer response. Preserve useful customer-safe details from the
baseline response draft, including its salutation. Do not promise an outcome that the control
record does not authorize.
""".strip()

OPENAI_DECISION_MAX_INPUT_CHARS = 24_000
OPENAI_DECISION_MAX_OUTPUT_TOKENS = 1_200


class DecisionNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(min_length=1, max_length=2000)
    uncertainty: str = Field(min_length=1, max_length=1000)
    response_subject: str = Field(min_length=1, max_length=300)
    response_body: str = Field(min_length=1, max_length=10_000)


class DecisionNarrativeGateway(Protocol):
    provider_name: str
    model_version: str

    def refine(self, analysis: DecisionAnalysis) -> DecisionNarrative: ...


class _ParsedResponse(Protocol):
    @property
    def output_parsed(self) -> DecisionNarrative | None: ...

    @property
    def usage(self) -> "_ResponseUsage | None": ...


class _InputTokenDetails(Protocol):
    @property
    def cached_tokens(self) -> int: ...

    @property
    def cache_write_tokens(self) -> int: ...


class _OutputTokenDetails(Protocol):
    @property
    def reasoning_tokens(self) -> int: ...


class _ResponseUsage(Protocol):
    @property
    def input_tokens(self) -> int: ...

    @property
    def input_tokens_details(self) -> _InputTokenDetails: ...

    @property
    def output_tokens(self) -> int: ...

    @property
    def output_tokens_details(self) -> _OutputTokenDetails: ...

    @property
    def total_tokens(self) -> int: ...


class _ResponsesResource(Protocol):
    def parse(self, **kwargs: Any) -> _ParsedResponse: ...


class _OpenAIClient(Protocol):
    @property
    def responses(self) -> _ResponsesResource: ...

    def close(self) -> None: ...


class OpenAIDecisionNarrativeGateway:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        client: _OpenAIClient | None = None,
        client_factory: Callable[[], _OpenAIClient] | None = None,
    ) -> None:
        self.model_version = model
        self._client = client
        self._usage_records: list[ProviderTokenUsage] = []
        self._client_factory = client_factory or (
            lambda: _build_openai_client(
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        )

    def refine(self, analysis: DecisionAnalysis) -> DecisionNarrative:
        try:
            messages = build_decision_narrative_messages(
                decision_narrative_control_record(analysis)
            )
        except DecisionNarrativePromptTooLarge as exc:
            raise ModelGatewayUnavailable(
                "AI narrative generation input exceeded the configured safety limit."
            ) from exc
        model_instructions = str(messages[0].content)
        model_input = str(messages[1].content)
        if len(model_input) > OPENAI_DECISION_MAX_INPUT_CHARS:
            raise ModelGatewayUnavailable(
                "AI narrative generation input exceeded the configured safety limit."
            )
        try:
            response = self._client_instance().responses.parse(
                model=cast(Any, self.model_version),
                instructions=model_instructions,
                input=model_input,
                text_format=DecisionNarrative,
                reasoning={"effort": "low"},
                max_output_tokens=OPENAI_DECISION_MAX_OUTPUT_TOKENS,
                store=False,
            )
        except ValidationError as exc:
            raise ModelGatewayUnavailable(
                "AI narrative generation returned an invalid structured result."
            ) from exc
        except Exception as exc:
            error_kind = _openai_error_kind(exc)
            if error_kind == "timeout":
                raise ModelGatewayTimeout("AI narrative generation timed out.") from exc
            if error_kind == "provider":
                raise ModelGatewayUnavailable("AI narrative generation is unavailable.") from exc
            raise

        usage = _provider_token_usage(response)
        if usage is not None:
            self._usage_records.append(usage)
        if response.output_parsed is None:
            raise ModelGatewayUnavailable("AI narrative generation returned no structured result.")
        return response.output_parsed

    @property
    def usage_records(self) -> tuple[ProviderTokenUsage, ...]:
        return tuple(self._usage_records)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _client_instance(self) -> _OpenAIClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client


def _build_openai_client(
    *,
    api_key: str,
    timeout_seconds: float,
    max_retries: int,
) -> _OpenAIClient:
    from openai import OpenAI

    return cast(
        _OpenAIClient,
        OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        ),
    )


def _openai_error_kind(error: Exception) -> str | None:
    from openai import APITimeoutError, OpenAIError

    if isinstance(error, APITimeoutError):
        return "timeout"
    if isinstance(error, OpenAIError):
        return "provider"
    return None


def _provider_token_usage(response: _ParsedResponse) -> ProviderTokenUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    input_details = usage.input_tokens_details
    output_details = usage.output_tokens_details
    return ProviderTokenUsage(
        input_tokens=usage.input_tokens,
        cached_input_tokens=input_details.cached_tokens,
        cache_write_input_tokens=input_details.cache_write_tokens,
        output_tokens=usage.output_tokens,
        reasoning_output_tokens=output_details.reasoning_tokens,
        total_tokens=usage.total_tokens,
    )


def decision_narrative_control_record(
    analysis: DecisionAnalysis,
) -> dict[str, object]:
    """Return the server-owned controls that narrative models may restate."""

    return {
        "proposal_state": analysis.state.value,
        "policy_status": analysis.policy_status.value,
        "facts": [fact.statement for fact in analysis.facts],
        "missing_information": [
            {
                "label": gap.label,
                "description": gap.description,
                "blocking": gap.blocking,
            }
            for gap in analysis.missing_information
        ],
        "risk_checks": [
            {
                "label": risk.label,
                "outcome": risk.outcome.value,
                "explanation": risk.explanation,
            }
            for risk in analysis.risks
        ],
        "proposed_outcome": analysis.outcome,
        "confidence": analysis.confidence.value,
        "uncertainty": analysis.uncertainty,
        "rationale": analysis.rationale,
        "actions": [
            {
                "type": action.type,
                "label": action.label,
                "impact_amount": action.impact_amount,
                "impact_currency": action.impact_currency,
                "expected_outcome": action.expected_outcome,
                "review_required": action.review_required,
            }
            for action in analysis.proposed_actions
        ],
        "response_draft": {
            "subject": analysis.response_draft.subject,
            "body": analysis.response_draft.body,
            "status": analysis.response_draft.status.value,
        },
    }
