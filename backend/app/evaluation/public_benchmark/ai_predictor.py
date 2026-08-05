import json
from collections.abc import Callable
from typing import Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from app.evaluation.public_benchmark.models import CfpbInputRecord, FosInputRecord
from app.evaluation.public_benchmark.storage import canonical_json_bytes, sha256_bytes

AI_PUBLIC_BENCHMARK_PROMPT_VERSION = "public-evidence-classifier-v2"
AI_PUBLIC_REQUEST_LAYOUT_VERSION = "task-in-instructions-record-values-only-v2"
AI_PUBLIC_BENCHMARK_INSTRUCTIONS = """
You are performing a bounded offline evaluation of support-escalation reasoning.
Use only the supplied public input record. The hidden answer is not available to you.

Choose only one of the allowed task labels. Choose "abstain" when the supplied record does
not support a responsible prediction. Do not treat an allegation as a verified fact.

Every evidence quote must be a short, exact, contiguous quote from the supplied record.
Quote only record values, never these instructions, task labels, or JSON field names.
Do not invent evidence, policy, money, people, actions, or events. This output is analysis
only. It cannot authorize, promise, execute, or imply completion of any operational action.
Human review is always required.
""".strip()

CFPB_TASK_INSTRUCTIONS = """
Predict the public company-response category from the complaint-side record:
- Closed with explanation
- Closed with monetary relief
- Closed with non-monetary relief
- abstain

This is a prediction of the eventual public response category, not a judgment that the
consumer's allegations are proven. Because post-intake company behavior is absent, abstain
when the complaint-side record is not enough.
""".strip()

FOS_TASK_INSTRUCTIONS = """
Predict the Financial Ombudsman Service disposition from the outcome-sanitized factual record:
- upheld
- partially_upheld
- not_upheld
- abstain

Use the pre-decision facts only. Do not assume omitted investigator or ombudsman reasoning.
""".strip()

ModelConfidence = Literal["low", "medium", "high"]
ProviderErrorCategory = Literal[
    "authentication",
    "interrupted",
    "invalid_output",
    "model_access",
    "rate_limit",
    "timeout",
    "provider",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CfpbPublicAssessment(StrictModel):
    company_response: Literal[
        "Closed with explanation",
        "Closed with monetary relief",
        "Closed with non-monetary relief",
        "abstain",
    ]
    confidence: ModelConfidence
    evidence_quotes: list[str] = Field(min_length=0, max_length=4)
    uncertainty: str = Field(min_length=1, max_length=500)
    review_required: Literal[True]
    action_status: Literal["analysis_only"]


class FosPublicAssessment(StrictModel):
    outcome: Literal["upheld", "partially_upheld", "not_upheld", "abstain"]
    confidence: ModelConfidence
    evidence_quotes: list[str] = Field(min_length=0, max_length=4)
    uncertainty: str = Field(min_length=1, max_length=500)
    review_required: Literal[True]
    action_status: Literal["analysis_only"]


PublicEvidenceAssessment = CfpbPublicAssessment | FosPublicAssessment


class ModelTokenUsage(StrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class PublicEvidenceResult(StrictModel):
    assessment: PublicEvidenceAssessment
    usage: ModelTokenUsage


class PublicEvidenceModelError(RuntimeError):
    def __init__(self, category: ProviderErrorCategory) -> None:
        super().__init__(f"Public evidence model request failed: {category}")
        self.category = category


class _Usage(Protocol):
    input_tokens: int
    output_tokens: int


class _ParsedResponse(Protocol):
    output_parsed: PublicEvidenceAssessment | None
    usage: _Usage | None


class _ResponsesResource(Protocol):
    def parse(self, **kwargs: Any) -> _ParsedResponse: ...


class _OpenAIClient(Protocol):
    @property
    def responses(self) -> _ResponsesResource: ...

    def close(self) -> None: ...


class OpenAIPublicEvidenceGateway:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int = 700,
        client: _OpenAIClient | None = None,
        client_factory: Callable[[], _OpenAIClient] | None = None,
    ) -> None:
        self.model_version = model
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self._client = client
        self._client_factory = client_factory or (
            lambda: _build_openai_client(
                api_key=api_key,
                timeout_seconds=timeout_seconds,
            )
        )

    def predict(
        self,
        record: CfpbInputRecord | FosInputRecord,
    ) -> PublicEvidenceResult:
        if isinstance(record, CfpbInputRecord):
            task = CFPB_TASK_INSTRUCTIONS
            response_type: type[CfpbPublicAssessment] | type[FosPublicAssessment] = (
                CfpbPublicAssessment
            )
        else:
            task = FOS_TASK_INSTRUCTIONS
            response_type = FosPublicAssessment
        model_input = record.payload.model_dump(mode="json", exclude_none=True)
        try:
            response = self._client_instance().responses.parse(
                model=cast(Any, self.model_version),
                instructions=f"{AI_PUBLIC_BENCHMARK_INSTRUCTIONS}\n\n{task}",
                input=json.dumps(
                    model_input,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
                text_format=response_type,
                reasoning={"effort": "low"},
                max_output_tokens=self.max_output_tokens,
                store=False,
            )
        except Exception as exc:
            category = _openai_error_category(exc)
            if category is None:
                raise
            raise PublicEvidenceModelError(category) from exc

        parsed = response.output_parsed
        if parsed is None or not isinstance(parsed, response_type):
            raise PublicEvidenceModelError("invalid_output")
        usage = response.usage
        return PublicEvidenceResult(
            assessment=parsed,
            usage=ModelTokenUsage(
                input_tokens=max(0, usage.input_tokens) if usage else 0,
                output_tokens=max(0, usage.output_tokens) if usage else 0,
            ),
        )

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _client_instance(self) -> _OpenAIClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client


def public_prompt_sha256() -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {
                "version": AI_PUBLIC_BENCHMARK_PROMPT_VERSION,
                "request_layout": AI_PUBLIC_REQUEST_LAYOUT_VERSION,
                "instructions": AI_PUBLIC_BENCHMARK_INSTRUCTIONS,
                "cfpb_task": CFPB_TASK_INSTRUCTIONS,
                "fos_task": FOS_TASK_INSTRUCTIONS,
                "schemas": {
                    "cfpb": CfpbPublicAssessment.model_json_schema(),
                    "fos": FosPublicAssessment.model_json_schema(),
                },
            }
        )
    )


def _build_openai_client(*, api_key: str, timeout_seconds: float) -> _OpenAIClient:
    from openai import OpenAI

    return cast(
        _OpenAIClient,
        OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        ),
    )


def _openai_error_category(error: Exception) -> ProviderErrorCategory | None:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        NotFoundError,
        RateLimitError,
    )

    if isinstance(error, AuthenticationError):
        return "authentication"
    if isinstance(error, NotFoundError):
        return "model_access"
    if isinstance(error, APITimeoutError):
        return "timeout"
    if isinstance(error, RateLimitError):
        return "rate_limit"
    if isinstance(error, (APIConnectionError, APIStatusError)):
        return "provider"
    return None
