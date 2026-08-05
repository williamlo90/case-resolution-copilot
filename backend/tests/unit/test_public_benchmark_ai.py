import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.evaluation.public_benchmark.ai_models import AIPublicBenchmarkReport
from app.evaluation.public_benchmark.ai_predictor import (
    CfpbPublicAssessment,
    FosPublicAssessment,
    ModelTokenUsage,
    OpenAIPublicEvidenceGateway,
    PublicEvidenceResult,
    public_prompt_sha256,
)
from app.evaluation.public_benchmark.ai_runner import (
    _exclusive_run_lock,
    generate_ai_predictions,
    score_ai_predictions,
)
from app.evaluation.public_benchmark.models import (
    CfpbInputPayload,
    CfpbInputRecord,
    FosInputRecord,
)
from tests.unit.test_public_benchmark_runner import _write_benchmark

NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
HASH = "a" * 64


class _Usage:
    input_tokens = 25
    output_tokens = 12


class _ParsedResponse:
    def __init__(self, output: CfpbPublicAssessment) -> None:
        self.output_parsed = output
        self.usage = _Usage()


class _Responses:
    def __init__(self, output: CfpbPublicAssessment) -> None:
        self.output = output
        self.arguments: dict[str, Any] | None = None

    def parse(self, **kwargs: Any) -> _ParsedResponse:
        self.arguments = kwargs
        return _ParsedResponse(self.output)


class _Client:
    def __init__(self, responses: _Responses) -> None:
        self.responses = responses
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _cfpb_input() -> CfpbInputRecord:
    return CfpbInputRecord(
        record_id="cfpb-ai-fixture",
        source_record_id="hidden-source-reference",
        source_url="https://example.test/cfpb",
        retrieved_at=NOW,
        source_artifact_sha256=HASH,
        payload=CfpbInputPayload(
            received_on=NOW.date(),
            product="Checking account",
            issue="Incorrect fee",
            submitted_via="Web",
            narrative="The customer says a duplicate fee was charged and requests a refund.",
        ),
    )


def _cfpb_assessment() -> CfpbPublicAssessment:
    return CfpbPublicAssessment(
        company_response="Closed with monetary relief",
        confidence="medium",
        evidence_quotes=["requests a refund"],
        uncertainty="The eventual company action is not present in the complaint.",
        review_required=True,
        action_status="analysis_only",
    )


def test_openai_public_gateway_sends_input_payload_without_source_metadata() -> None:
    responses = _Responses(_cfpb_assessment())
    client = _Client(responses)
    gateway = OpenAIPublicEvidenceGateway(
        api_key="unused-test-key",
        model="test-model",
        timeout_seconds=30,
        client=cast(Any, client),
    )

    result = gateway.predict(_cfpb_input())

    assert result.assessment == _cfpb_assessment()
    assert result.usage == ModelTokenUsage(input_tokens=25, output_tokens=12)
    assert responses.arguments is not None
    serialized = json.loads(responses.arguments["input"])
    assert serialized["narrative"].startswith("The customer says")
    assert "hidden-source-reference" not in responses.arguments["input"]
    assert "source_url" not in responses.arguments["input"]
    assert "post-intake company behavior" not in responses.arguments["input"]
    assert "post-intake company behavior" in responses.arguments["instructions"]
    assert responses.arguments["store"] is False
    assert responses.arguments["reasoning"] == {"effort": "low"}
    gateway.close()
    assert client.closed is True


def test_public_assessment_schema_enforces_human_review_boundary() -> None:
    payload = _cfpb_assessment().model_dump()
    payload["review_required"] = False

    with pytest.raises(ValidationError):
        CfpbPublicAssessment.model_validate(payload)


class _FakeGateway:
    provider_name = "openai"
    model_version = "fixture-model"
    timeout_seconds = 30.0
    max_output_tokens = 400

    def __init__(self) -> None:
        self.calls: list[str] = []

    def predict(
        self,
        record: CfpbInputRecord | FosInputRecord,
    ) -> PublicEvidenceResult:
        self.calls.append(record.record_id)
        assessment: CfpbPublicAssessment | FosPublicAssessment
        if isinstance(record, CfpbInputRecord):
            assessment = CfpbPublicAssessment(
                company_response="Closed with monetary relief",
                confidence="medium",
                evidence_quotes=["requests a refund"],
                uncertainty="The company response is not included in the complaint.",
                review_required=True,
                action_status="analysis_only",
            )
        else:
            assessment = FosPublicAssessment(
                outcome="upheld",
                confidence="medium",
                evidence_quotes=["reported a scam"],
                uncertainty="The final ombudsman reasoning is intentionally absent.",
                review_required=True,
                action_status="analysis_only",
            )
        return PublicEvidenceResult(
            assessment=assessment,
            usage=ModelTokenUsage(input_tokens=50, output_tokens=20),
        )


class _InterruptingGateway(_FakeGateway):
    def predict(
        self,
        record: CfpbInputRecord | FosInputRecord,
    ) -> PublicEvidenceResult:
        self.calls.append(record.record_id)
        raise KeyboardInterrupt


def test_ai_runner_is_input_only_resumable_and_scores_after_prediction(
    tmp_path: Path,
) -> None:
    _write_benchmark(tmp_path)
    label_paths = [
        tmp_path / "prepared" / suite / "labels.jsonl"
        for suite in ("cfpb", "fos", "uci")
    ]
    hidden_paths = [path.with_suffix(".hidden") for path in label_paths]
    for source, hidden in zip(label_paths, hidden_paths, strict=True):
        source.rename(hidden)
    gateway = _FakeGateway()

    first = generate_ai_predictions(
        tmp_path,
        gateway=gateway,
        run_id="test-ai-run-v1",
        model_call_budget=2,
        clock=lambda: NOW,
    )
    second = generate_ai_predictions(
        tmp_path,
        gateway=gateway,
        run_id="test-ai-run-v1",
        model_call_budget=2,
        clock=lambda: NOW,
    )

    assert len(gateway.calls) == 2
    assert gateway.calls[0].startswith("fos-")
    assert first.predictions.sha256 == second.predictions.sha256
    assert first.model_calls_started == 2
    assert first.predictions.records == 4
    for hidden, destination in zip(hidden_paths, label_paths, strict=True):
        hidden.rename(destination)

    report = score_ai_predictions(
        tmp_path,
        run_id="test-ai-run-v1",
        clock=lambda: NOW,
    )

    assert isinstance(report, AIPublicBenchmarkReport)
    assert [suite.suite for suite in report.suites] == ["cfpb", "fos", "uci"]
    assert all(suite.accuracy == 1 for suite in report.suites)
    assert report.safety.approval_boundary_preservation_rate == 1
    assert report.safety.unsafe_action_rate == 0
    serialized = report.model_dump(mode="json")
    assert "overall_accuracy" not in serialized
    assert report.prompt_sha256 == public_prompt_sha256()


def test_ai_runner_does_not_retry_an_interrupted_in_flight_record(
    tmp_path: Path,
) -> None:
    _write_benchmark(tmp_path)
    interrupted = _InterruptingGateway()

    with pytest.raises(KeyboardInterrupt):
        generate_ai_predictions(
            tmp_path,
            gateway=interrupted,
            run_id="test-ai-interrupted-v1",
            model_call_budget=2,
            clock=lambda: NOW,
        )

    resumed = _FakeGateway()
    manifest = generate_ai_predictions(
        tmp_path,
        gateway=resumed,
        run_id="test-ai-interrupted-v1",
        model_call_budget=2,
        clock=lambda: NOW,
    )
    report = score_ai_predictions(
        tmp_path,
        run_id="test-ai-interrupted-v1",
        clock=lambda: NOW,
    )
    fos = next(suite for suite in report.suites if suite.suite == "fos")

    assert len(interrupted.calls) == 1
    assert len(resumed.calls) == 1
    assert resumed.calls[0].startswith("cfpb-")
    assert manifest.model_calls_started == 2
    assert fos.abstention_rate == 1
    assert fos.schema_validity_rate == 0


def test_ai_runner_rejects_a_second_prediction_process(tmp_path: Path) -> None:
    _write_benchmark(tmp_path)
    gateway = _FakeGateway()
    lock_path = tmp_path / "runs" / "test-ai-locked-v1" / "prediction.lock"

    with (
        _exclusive_run_lock(lock_path),
        pytest.raises(RuntimeError, match="already holds"),
    ):
        generate_ai_predictions(
            tmp_path,
            gateway=gateway,
            run_id="test-ai-locked-v1",
            model_call_budget=2,
            clock=lambda: NOW,
        )

    assert gateway.calls == []
