from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from app.evaluation.public_benchmark.ai_generation import (
    DEFAULT_AI_RUN_ID,
    SUITES,
    evidence_text,
    index_unique,
    load_inputs,
    quote_is_supported,
    run_root_for,
    utc_now,
)
from app.evaluation.public_benchmark.ai_models import (
    AI_PREDICTION_ADAPTER,
    AICfpbPredictionRecord,
    AIEvaluationContract,
    AIFosPredictionRecord,
    AIPredictionManifest,
    AIPredictionRecord,
    AIPublicBenchmarkReport,
    AISafetyMetrics,
    AISuiteMetrics,
    AIUciPredictionRecord,
    AIUsageSummary,
)
from app.evaluation.public_benchmark.baseline import input_fingerprint
from app.evaluation.public_benchmark.models import (
    BENCHMARK_LABEL_ADAPTER,
    BenchmarkInputRecord,
    BenchmarkLabelRecord,
    CfpbInputRecord,
    CfpbLabelRecord,
    FosInputRecord,
    FosLabelRecord,
    SuiteName,
    UciLabelRecord,
)
from app.evaluation.public_benchmark.predictions import InputSnapshot, RunArtifact
from app.evaluation.public_benchmark.storage import (
    atomic_write_bytes,
    atomic_write_json,
    ensure_within,
    read_jsonl,
    relative_manifest_path,
    sha256_file,
)
from app.evaluation.public_benchmark.validation import validate_public_benchmark

_CFPB_LABELS = (
    "Closed with explanation",
    "Closed with monetary relief",
    "Closed with non-monetary relief",
)
_FOS_LABELS = ("upheld", "partially_upheld", "not_upheld")
_UCI_LABELS = ("candidate_cancellation_match", "unrelated_pair")


def score_ai_predictions(
    data_root: Path,
    *,
    run_id: str = DEFAULT_AI_RUN_ID,
    clock: Callable[[], datetime] | None = None,
) -> AIPublicBenchmarkReport:
    from app.evaluation.public_benchmark.ai_models import AI_RUN_ID_ADAPTER

    validated_run_id = AI_RUN_ID_ADAPTER.validate_python(run_id)
    root = data_root.resolve()
    run_root = run_root_for(root, validated_run_id)
    manifest_path = ensure_within(root, run_root / "prediction-manifest.json")
    contract_path = ensure_within(root, run_root / "contract.json")
    if not manifest_path.is_file() or not contract_path.is_file():
        raise ValueError("Completed AI prediction artifacts are required before scoring.")
    manifest = AIPredictionManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    contract = AIEvaluationContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    if manifest.run_id != validated_run_id or contract.run_id != validated_run_id:
        raise ValueError("AI benchmark run ID does not match its directory.")
    if sha256_file(contract_path) != manifest.contract_sha256:
        raise ValueError("Frozen AI evaluation contract changed after prediction.")
    source_manifest = ensure_within(root, root / "manifest.json")
    if sha256_file(source_manifest) != manifest.source_manifest_sha256:
        raise ValueError("Prepared benchmark manifest changed after AI prediction.")
    inputs, snapshots = load_inputs(root)
    if snapshots != manifest.input_snapshots:
        raise ValueError("Benchmark input artifacts changed after AI prediction.")
    predictions_path = ensure_within(root, root / manifest.predictions.path)
    _validate_artifact(predictions_path, manifest.predictions, "prediction")
    predictions = read_jsonl(predictions_path, AI_PREDICTION_ADAPTER)
    if len(predictions) != manifest.predictions.records:
        raise ValueError("AI prediction record count changed.")

    validate_public_benchmark(root, require_manifest=True)
    labels, label_snapshots = _load_labels(root)
    input_by_id = index_unique(inputs, "input")
    prediction_by_id = index_unique(predictions, "prediction")
    label_by_id = index_unique(labels, "label")
    if input_by_id.keys() != prediction_by_id.keys():
        raise ValueError("AI prediction IDs do not match frozen inputs.")
    if input_by_id.keys() != label_by_id.keys():
        raise ValueError("Benchmark label IDs do not match frozen inputs.")
    for record_id, prediction in prediction_by_id.items():
        if prediction.input_sha256 != input_fingerprint(input_by_id[record_id]):
            raise ValueError(f"AI prediction input fingerprint mismatch for {record_id}.")
        if prediction.prompt_sha256 != manifest.prompt_sha256:
            raise ValueError(f"AI prediction prompt fingerprint mismatch for {record_id}.")
        if prediction.suite != label_by_id[record_id].suite:
            raise ValueError(f"AI prediction and label suite mismatch for {record_id}.")

    suites = [
        _score_cfpb(predictions, labels, input_by_id),
        _score_fos(predictions, labels, input_by_id),
        _score_uci(predictions, labels),
    ]
    model_predictions = [
        item
        for item in predictions
        if isinstance(item, (AICfpbPredictionRecord, AIFosPredictionRecord))
    ]
    safe_outputs = [
        item.payload.review_required and item.payload.action_status == "analysis_only"
        for item in model_predictions
    ]
    safety = AISafetyMetrics(
        model_records=len(model_predictions),
        approval_boundary_preservation_rate=_mean(safe_outputs),
        unsafe_action_rate=_mean([not value for value in safe_outputs]),
    )
    report = AIPublicBenchmarkReport(
        run_id=validated_run_id,
        scored_at=(clock or utc_now)(),
        predictor=manifest.predictor,
        predictor_version=manifest.predictor_version,
        model=manifest.model,
        prompt_sha256=manifest.prompt_sha256,
        contract_sha256=manifest.contract_sha256,
        prediction_manifest_sha256=sha256_file(manifest_path),
        label_snapshots=label_snapshots,
        suites=suites,
        safety=safety,
        usage=AIUsageSummary(
            model_calls_started=manifest.model_calls_started,
            input_tokens=manifest.input_tokens,
            output_tokens=manifest.output_tokens,
        ),
        integrity_checks=[
            "evaluation_contract_frozen_before_model_calls",
            "prediction_phase_used_input_files_only",
            "labels_opened_only_after_predictions_finalized",
            "source_manifest_unchanged",
            "input_artifact_hashes_unchanged",
            "prediction_artifact_hash_matches",
            "prediction_input_fingerprints_match",
            "structured_outputs_validated_server_side",
            "model_requests_serial_with_zero_sdk_retries",
            "model_call_budget_not_exceeded",
            "uci_remained_deterministic",
            "suite_boundaries_preserved",
            "no_cross_suite_aggregate_score",
        ],
        permitted_claim=(
            "The configured model completed a recorded input-only evaluation on separate real "
            "public FOS and CFPB records, while UCI matching remained deterministic."
        ),
        limitations=[
            "This model-capability evaluation is separate from the production Decision Brief "
            "engine, whose outcome and approval controls remain deterministic.",
            "The three public suites are not joined and are not complete business case files.",
            "CFPB response categories depend partly on company behavior after intake and are not "
            "fully inferable from complaint-side records.",
            "The ten FOS decisions are a small engineering sample, not a statistical or legal "
            "benchmark.",
            "Approval-boundary and unsafe-action metrics are contract-enforced safety invariants, "
            "not evidence that unconstrained model output is safe.",
            "This run does not validate a live client workflow or production integration.",
        ],
    )
    atomic_write_json(root, run_root / "report.json", report.model_dump(mode="json"))
    atomic_write_bytes(
        root,
        run_root / "report.md",
        _render_markdown(report).encode("utf-8"),
    )
    return report


def _score_cfpb(
    predictions: Sequence[AIPredictionRecord],
    labels: Sequence[BenchmarkLabelRecord],
    input_by_id: dict[str, BenchmarkInputRecord],
) -> AISuiteMetrics:
    predicted = {
        item.record_id: item
        for item in predictions
        if isinstance(item, AICfpbPredictionRecord)
    }
    expected = [item for item in labels if isinstance(item, CfpbLabelRecord)]
    return _text_suite_metrics(
        suite="cfpb",
        task="Predict public company-response category from the complaint-side record.",
        expected=[item.payload.company_response for item in expected],
        predicted=[predicted[item.record_id] for item in expected],
        predicted_values=[
            predicted[item.record_id].payload.company_response for item in expected
        ],
        input_by_id=input_by_id,
        labels=_CFPB_LABELS,
        interpretation=(
            "Exploratory only: the target includes post-intake company behavior that is absent "
            "from the complaint-side input."
        ),
    )


def _score_fos(
    predictions: Sequence[AIPredictionRecord],
    labels: Sequence[BenchmarkLabelRecord],
    input_by_id: dict[str, BenchmarkInputRecord],
) -> AISuiteMetrics:
    predicted = {
        item.record_id: item
        for item in predictions
        if isinstance(item, AIFosPredictionRecord)
    }
    expected = [item for item in labels if isinstance(item, FosLabelRecord)]
    return _text_suite_metrics(
        suite="fos",
        task="Predict final complaint disposition from the outcome-sanitized factual record.",
        expected=[item.payload.outcome for item in expected],
        predicted=[predicted[item.record_id] for item in expected],
        predicted_values=[predicted[item.record_id].payload.outcome for item in expected],
        input_by_id=input_by_id,
        labels=_FOS_LABELS,
        interpretation=(
            "This small outcome-sanitized engineering sample tests disposition reasoning and "
            "evidence grounding, not legal reliability."
        ),
    )


def _score_uci(
    predictions: Sequence[AIPredictionRecord],
    labels: Sequence[BenchmarkLabelRecord],
) -> AISuiteMetrics:
    predicted = {
        item.record_id: item
        for item in predictions
        if isinstance(item, AIUciPredictionRecord)
    }
    expected = [item for item in labels if isinstance(item, UciLabelRecord)]
    expected_values = [item.payload.relationship for item in expected]
    predicted_values = [
        predicted[item.record_id].payload.relationship for item in expected
    ]
    positive = "candidate_cancellation_match"
    true_positive = sum(
        expected_value == positive and predicted_value == positive
        for expected_value, predicted_value in zip(
            expected_values, predicted_values, strict=True
        )
    )
    false_positive = sum(
        expected_value != positive and predicted_value == positive
        for expected_value, predicted_value in zip(
            expected_values, predicted_values, strict=True
        )
    )
    false_negative = sum(
        expected_value == positive and predicted_value != positive
        for expected_value, predicted_value in zip(
            expected_values, predicted_values, strict=True
        )
    )
    precision = _divide(true_positive, true_positive + false_positive)
    recall = _divide(true_positive, true_positive + false_negative)
    positive_f1 = _divide(2 * precision * recall, precision + recall)
    matched = [item for item in expected if item.payload.relationship == positive]
    invoice_accuracy = _mean(
        [
            predicted[item.record_id].payload.expected_original_invoice
            == item.payload.expected_original_invoice
            for item in matched
        ]
    )
    base = _categorical_metrics(
        expected=expected_values,
        predicted=predicted_values,
        labels=_UCI_LABELS,
    )
    return AISuiteMetrics(
        suite="uci",
        task="Link a cancellation row to its candidate original sale using explicit fields.",
        records=len(expected_values),
        accuracy=base["accuracy"],
        macro_f1=base["macro_f1"],
        abstention_rate=0,
        schema_validity_rate=1,
        unsupported_evidence_quote_rate=0,
        expected_distribution=dict(Counter(expected_values)),
        predicted_distribution=dict(Counter(predicted_values)),
        confusion_matrix=base["confusion_matrix"],
        secondary_metrics={
            "candidate_match_precision": precision,
            "candidate_match_recall": recall,
            "candidate_match_f1": positive_f1,
            "matched_invoice_accuracy": invoice_accuracy,
        },
        interpretation=(
            "This deterministic exact-field task validates adapter matching, not model reasoning."
        ),
    )


def _text_suite_metrics(
    *,
    suite: SuiteName,
    task: str,
    expected: list[str],
    predicted: list[AICfpbPredictionRecord] | list[AIFosPredictionRecord],
    predicted_values: list[str],
    input_by_id: dict[str, BenchmarkInputRecord],
    labels: tuple[str, ...],
    interpretation: str,
) -> AISuiteMetrics:
    base = _categorical_metrics(
        expected=expected,
        predicted=predicted_values,
        labels=labels,
        extra_predictions=("abstain",),
    )
    quote_count = sum(len(item.payload.evidence_quotes) for item in predicted)
    unsupported_count = 0
    for item in predicted:
        source = input_by_id[item.record_id]
        if not isinstance(source, (CfpbInputRecord, FosInputRecord)):
            raise ValueError("Text prediction references a non-text benchmark input.")
        unsupported_count += sum(
            not quote_is_supported(quote, evidence_text(source))
            for quote in item.payload.evidence_quotes
        )
    answered = [
        expected_value == predicted_value
        for expected_value, predicted_value in zip(
            expected,
            predicted_values,
            strict=True,
        )
        if predicted_value != "abstain"
    ]
    abstention_rate = _mean([value == "abstain" for value in predicted_values])
    return AISuiteMetrics(
        suite=suite,
        task=task,
        records=len(expected),
        accuracy=base["accuracy"],
        macro_f1=base["macro_f1"],
        abstention_rate=abstention_rate,
        schema_validity_rate=_mean([item.payload.schema_valid for item in predicted]),
        unsupported_evidence_quote_rate=_divide(unsupported_count, quote_count),
        expected_distribution=dict(Counter(expected)),
        predicted_distribution=dict(Counter(predicted_values)),
        confusion_matrix=base["confusion_matrix"],
        secondary_metrics={
            "coverage": 1 - abstention_rate,
            "accuracy_on_answered": _mean(answered),
            "evidence_quotes": float(quote_count),
            "unsupported_evidence_quotes": float(unsupported_count),
        },
        interpretation=interpretation,
    )


def _categorical_metrics(
    *,
    expected: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str],
    extra_predictions: Sequence[str] = (),
) -> dict[str, object]:
    if not expected or len(expected) != len(predicted):
        raise ValueError("Categorical metrics require aligned, non-empty values.")
    predicted_labels = [*labels, *extra_predictions]
    confusion = {
        label: {predicted_label: 0 for predicted_label in predicted_labels}
        for label in labels
    }
    for expected_value, predicted_value in zip(expected, predicted, strict=True):
        if expected_value not in confusion or predicted_value not in predicted_labels:
            raise ValueError("Unsupported benchmark score label.")
        confusion[expected_value][predicted_value] += 1
    f1_values: list[float] = []
    for label in labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[other][label] for other in labels if other != label)
        false_negative = sum(
            confusion[label][other] for other in predicted_labels if other != label
        )
        precision = _divide(true_positive, true_positive + false_positive)
        recall = _divide(true_positive, true_positive + false_negative)
        f1_values.append(_divide(2 * precision * recall, precision + recall))
    return {
        "accuracy": _mean(
            [
                expected_value == predicted_value
                for expected_value, predicted_value in zip(
                    expected, predicted, strict=True
                )
            ]
        ),
        "macro_f1": sum(f1_values) / len(f1_values),
        "confusion_matrix": confusion,
    }


def _load_labels(
    root: Path,
) -> tuple[list[BenchmarkLabelRecord], list[InputSnapshot]]:
    records: list[BenchmarkLabelRecord] = []
    snapshots: list[InputSnapshot] = []
    for suite in SUITES:
        path = ensure_within(root, root / "prepared" / suite / "labels.jsonl")
        if not path.is_file():
            raise ValueError(f"Prepared {suite} labels are required for scoring.")
        suite_records = read_jsonl(path, BENCHMARK_LABEL_ADAPTER)
        if not suite_records or any(record.suite != suite for record in suite_records):
            raise ValueError(f"Prepared {suite} label boundary is invalid.")
        records.extend(suite_records)
        snapshots.append(
            InputSnapshot(
                suite=suite,
                path=relative_manifest_path(root, path),
                sha256=sha256_file(path),
                bytes=path.stat().st_size,
                records=len(suite_records),
            )
        )
    return records, snapshots


def _validate_artifact(path: Path, artifact: RunArtifact, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label.title()} artifact is missing.")
    if path.stat().st_size != artifact.bytes:
        raise ValueError(f"{label.title()} artifact byte count changed.")
    if sha256_file(path) != artifact.sha256:
        raise ValueError(f"{label.title()} artifact hash changed.")


def _mean(values: Sequence[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _render_markdown(report: AIPublicBenchmarkReport) -> str:
    lines = [
        "# Public Evidence AI Evaluation",
        "",
        f"- Run: `{report.run_id}`",
        f"- Model: `{report.model}`",
        f"- Prompt SHA-256: `{report.prompt_sha256}`",
        f"- Contract SHA-256: `{report.contract_sha256}`",
        f"- Prediction manifest: `{report.prediction_manifest_sha256}`",
        "",
        "## Results",
        "",
        "| Suite | Records | Accuracy | Macro F1 | Abstain | Schema valid | "
        "Unsupported quote |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(
        (
            f"| {suite.suite.upper()} | {suite.records} | {suite.accuracy:.3f} | "
            f"{suite.macro_f1:.3f} | {suite.abstention_rate:.3f} | "
            f"{suite.schema_validity_rate:.3f} | "
            f"{suite.unsupported_evidence_quote_rate:.3f} |"
        )
        for suite in report.suites
    )
    lines.extend(
        [
            "",
            "There is no cross-suite aggregate because the tasks have different semantics.",
            "",
            "## Safety Contract",
            "",
            (
                "- Approval boundary preserved: "
                f"`{report.safety.approval_boundary_preservation_rate:.3f}`"
            ),
            f"- Unsafe action rate: `{report.safety.unsafe_action_rate:.3f}`",
            "- Enforcement: structured output plus server validation.",
            "",
            "## Usage",
            "",
            f"- Model calls started: `{report.usage.model_calls_started}`",
            f"- Input tokens reported by provider: `{report.usage.input_tokens}`",
            f"- Output tokens reported by provider: `{report.usage.output_tokens}`",
            "",
            "## Integrity",
            "",
            *[f"- {check}" for check in report.integrity_checks],
            "",
            "## Permitted Claim",
            "",
            report.permitted_claim,
            "",
            "## Limitations",
            "",
            *[f"- {limitation}" for limitation in report.limitations],
            "",
        ]
    )
    return "\n".join(lines)
