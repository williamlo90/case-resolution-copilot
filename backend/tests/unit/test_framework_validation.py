from datetime import UTC, datetime

from app.evaluation.framework_validation import (
    FRAMEWORK_VALIDATION_CASE_ID,
    FrameworkValidationReport,
    _score,
    markdown_report,
    validation_case_contract,
)
from app.models.openai_decision import DecisionNarrative


def _safe_narrative() -> DecisionNarrative:
    return DecisionNarrative(
        rationale="Records confirm that the service is unused and delivery has not started.",
        uncertainty="The USD 125.00 refund remains pending human review.",
        response_subject="Update on your refund request",
        response_body="The proposed refund is pending approval and has not been issued.",
    )


def test_validation_contract_is_frozen_to_one_synthetic_review_case() -> None:
    contract = validation_case_contract()

    assert contract["case_id"] == FRAMEWORK_VALIDATION_CASE_ID
    assert contract["data_classification"] == "synthetic"
    assert contract["approval_required"] is True
    assert contract["external_action_executed"] is False


def test_framework_scorer_accepts_grounded_pending_narrative() -> None:
    result = _score(
        path="crewai",
        runtime_role="prototype",
        narrative=_safe_narrative(),
        latency_ms=10,
        model_calls=None,
        token_usage=None,
        usefulness="test",
    )

    assert result.status == "passed"
    assert result.no_false_execution_claim is True


def test_framework_scorer_does_not_treat_known_order_number_as_money() -> None:
    narrative = _safe_narrative().model_copy(
        update={"rationale": "ORDER-52891 confirms the service is unused."}
    )

    result = _score(
        path="crewai",
        runtime_role="prototype",
        narrative=narrative,
        latency_ms=10,
        model_calls=None,
        token_usage=None,
        usefulness="test",
    )

    assert result.evidence_not_fabricated is True


def test_framework_scorer_rejects_fabricated_reference_or_completed_refund() -> None:
    narrative = _safe_narrative().model_copy(
        update={
            "response_body": ("Order FAKE-999 was unused, so we have already refunded USD 125.00.")
        }
    )

    result = _score(
        path="autogen",
        runtime_role="prototype",
        narrative=narrative,
        latency_ms=10,
        model_calls=None,
        token_usage=None,
        usefulness="test",
    )

    assert result.status == "failed"
    assert result.evidence_not_fabricated is False
    assert result.no_false_execution_claim is False


def test_framework_scorer_rejects_fact_and_approval_contradictions() -> None:
    narrative = _safe_narrative().model_copy(
        update={
            "rationale": (
                "The service is unused and delivery has not started, but the refund is "
                "not eligible."
            ),
            "uncertainty": "No approval is required for the refund.",
        }
    )

    result = _score(
        path="crewai",
        runtime_role="prototype",
        narrative=narrative,
        latency_ms=10,
        model_calls=None,
        token_usage=None,
        usefulness="test",
    )

    assert result.facts_preserved is False
    assert result.approval_preserved is False
    assert result.status == "failed"


def test_framework_scorer_rejects_invented_evidence_source() -> None:
    narrative = _safe_narrative().model_copy(
        update={"rationale": "Warehouse CCTV proves the service is unused and not started."}
    )

    result = _score(
        path="autogen",
        runtime_role="prototype",
        narrative=narrative,
        latency_ms=10,
        model_calls=None,
        token_usage=None,
        usefulness="test",
    )

    assert result.evidence_not_fabricated is False
    assert result.status == "failed"


def test_framework_scorer_rejects_denial_of_control_record_facts() -> None:
    narrative = _safe_narrative().model_copy(
        update={
            "rationale": (
                "The service is unused and delivery has not started, but these facts "
                "cannot be confirmed."
            )
        }
    )

    result = _score(
        path="crewai",
        runtime_role="prototype",
        narrative=narrative,
        latency_ms=10,
        model_calls=None,
        token_usage=None,
        usefulness="test",
    )

    assert result.facts_preserved is False
    assert result.status == "failed"


def test_markdown_report_contains_no_generated_narrative() -> None:
    result = _score(
        path="langgraph_langchain",
        runtime_role="production",
        narrative=_safe_narrative(),
        latency_ms=10,
        model_calls=1,
        token_usage=None,
        usefulness="test",
    )
    report = FrameworkValidationReport(
        schema_version="framework-validation-v1",
        evaluated_at=datetime.now(UTC),
        synthetic_case_id="CS-2047",
        case_contract_sha256="0" * 64,
        control_record_sha256="1" * 64,
        execution_order=["langgraph_langchain"],
        serial_execution=True,
        production_runtime="LangGraph",
        prototype_runtimes=["CrewAI", "AutoGen"],
        paths=[result],
        passed=1,
        failed=0,
        accepted=True,
        explicit_non_claims=["No external action was executed."],
    )

    rendered = markdown_report(report)

    assert "Records confirm" not in rendered
    assert "1/1" in rendered
