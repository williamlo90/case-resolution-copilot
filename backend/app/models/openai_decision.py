import json
from collections.abc import Callable
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from app.domain.decision_briefs import DecisionAnalysis
from app.models.gateway import ModelGatewayTimeout, ModelGatewayUnavailable

OPENAI_DECISION_INSTRUCTIONS = """
Draft clear support decision language from the supplied server-generated control record.
Use plain business language and short sentences.

The server-owned facts, policy status, risk checks, proposed outcome, financial impact,
actions, and approval requirements are authoritative. Do not add, remove, or change them.
Do not invent customer details, policy clauses, evidence, amounts, or completed actions.
Never claim that an action has already happened. Make the response draft clear that any
review-required action remains pending human approval.
""".strip()


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
    output_parsed: DecisionNarrative | None


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
        self._client_factory = client_factory or (
            lambda: _build_openai_client(
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        )

    def refine(self, analysis: DecisionAnalysis) -> DecisionNarrative:
        try:
            response = self._client_instance().responses.parse(
                model=cast(Any, self.model_version),
                instructions=OPENAI_DECISION_INSTRUCTIONS,
                input=json.dumps(
                    _minimized_control_record(analysis),
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
                text_format=DecisionNarrative,
                reasoning={"effort": "low"},
                max_output_tokens=1200,
                store=False,
            )
        except Exception as exc:
            error_kind = _openai_error_kind(exc)
            if error_kind == "timeout":
                raise ModelGatewayTimeout("AI narrative generation timed out.") from exc
            if error_kind == "provider":
                raise ModelGatewayUnavailable("AI narrative generation is unavailable.") from exc
            raise

        if response.output_parsed is None:
            raise ModelGatewayUnavailable(
                "AI narrative generation returned no structured result."
            )
        return response.output_parsed

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


def _minimized_control_record(analysis: DecisionAnalysis) -> dict[str, object]:
    return {
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
