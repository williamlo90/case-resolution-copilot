from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.public_benchmark.baseline import DeterministicPublicBaseline
from app.evaluation.public_benchmark.models import (
    BENCHMARK_INPUT_ADAPTER,
    BENCHMARK_LABEL_ADAPTER,
    BenchmarkInputRecord,
    BenchmarkLabelRecord,
    CfpbLabelRecord,
    FosLabelRecord,
    SuiteName,
    UciLabelRecord,
)
from app.evaluation.public_benchmark.predictions import (
    BENCHMARK_PREDICTION_ADAPTER,
    RUN_ID_ADAPTER,
    BenchmarkPredictionRecord,
    CfpbPredictionRecord,
    FosPredictionRecord,
    InputSnapshot,
    PredictionRunManifest,
    PublicBenchmarkReport,
    RunArtifact,
    RunId,
    SuiteMetrics,
    UciPredictionRecord,
)
from app.evaluation.public_benchmark.storage import (
    atomic_write_bytes,
    atomic_write_json,
    ensure_within,
    read_jsonl,
    relative_manifest_path,
    sha256_file,
    write_jsonl,
)
from app.evaluation.public_benchmark.validation import validate_public_benchmark

_SUITES: tuple[SuiteName, ...] = ("cfpb", "fos", "uci")
_SUITE_ORDER = {suite: index for index, suite in enumerate(_SUITES)}
_CFPB_LABELS = (
    "Closed with explanation",
    "Closed with monetary relief",
    "Closed with non-monetary relief",
)
_FOS_LABELS = ("upheld", "partially_upheld", "not_upheld")
_UCI_LABELS = ("candidate_cancellation_match", "unrelated_pair")


def run_public_benchmark(
    data_root: Path,
    *,
    run_id: RunId = "deterministic-baseline-v1",
    clock: Callable[[], datetime] | None = None,
) -> PublicBenchmarkReport:
    generate_predictions(data_root, run_id=run_id, clock=clock)
    return score_predictions(data_root, run_id=run_id, clock=clock)


def generate_predictions(
    data_root: Path,
    *,
    run_id: RunId = "deterministic-baseline-v1",
    clock: Callable[[], datetime] | None = None,
) -> PredictionRunManifest:
    run_id = RUN_ID_ADAPTER.validate_python(run_id)
    root = data_root.resolve()
    source_manifest = ensure_within(root, root / "manifest.json")
    if not source_manifest.is_file():
        raise ValueError("Prepared benchmark manifest is required before prediction.")
    now = (clock or _utc_now)()
    predictor = DeterministicPublicBaseline()
    inputs, snapshots = _load_inputs(root)
    predictions = [predictor.predict(record) for record in inputs]
    run_root = _run_root(root, run_id)
    predictions_path = run_root / "predictions.jsonl"
    count = write_jsonl(root, predictions_path, predictions)
    prediction_artifact = RunArtifact(
        path=relative_manifest_path(root, predictions_path),
        sha256=sha256_file(predictions_path),
        bytes=predictions_path.stat().st_size,
        records=count,
    )
    manifest = PredictionRunManifest(
        run_id=run_id,
        generated_at=now,
        predictor=predictor.name,
        predictor_version=predictor.version,
        source_manifest_sha256=sha256_file(source_manifest),
        input_snapshots=snapshots,
        predictions=prediction_artifact,
    )
    atomic_write_json(
        root,
        run_root / "prediction-manifest.json",
        manifest.model_dump(mode="json"),
    )
    return manifest


def score_predictions(
    data_root: Path,
    *,
    run_id: RunId = "deterministic-baseline-v1",
    clock: Callable[[], datetime] | None = None,
) -> PublicBenchmarkReport:
    run_id = RUN_ID_ADAPTER.validate_python(run_id)
    root = data_root.resolve()
    run_root = _run_root(root, run_id)
    manifest_path = ensure_within(root, run_root / "prediction-manifest.json")
    if not manifest_path.is_file():
        raise ValueError("Prediction manifest is required before scoring.")
    manifest = PredictionRunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.run_id != run_id:
        raise ValueError("Prediction manifest run ID does not match its directory.")
    source_manifest = ensure_within(root, root / "manifest.json")
    if sha256_file(source_manifest) != manifest.source_manifest_sha256:
        raise ValueError("Prepared benchmark manifest changed after prediction.")
    inputs, current_input_snapshots = _load_inputs(root)
    if current_input_snapshots != manifest.input_snapshots:
        raise ValueError("Benchmark input artifacts changed after prediction.")
    predictions_path = ensure_within(root, root / manifest.predictions.path)
    _validate_artifact(predictions_path, manifest.predictions, "prediction")
    predictions = read_jsonl(predictions_path, BENCHMARK_PREDICTION_ADAPTER)
    if len(predictions) != manifest.predictions.records:
        raise ValueError("Prediction artifact record count changed.")
    validate_public_benchmark(root, require_manifest=True)
    labels, label_snapshots = _load_labels(root)
    input_by_id = _index_unique(inputs, "input")
    prediction_by_id = _index_unique(predictions, "prediction")
    label_by_id = _index_unique(labels, "label")
    if input_by_id.keys() != prediction_by_id.keys():
        raise ValueError("Prediction IDs do not match the frozen benchmark inputs.")
    if input_by_id.keys() != label_by_id.keys():
        raise ValueError("Label IDs do not match the frozen benchmark inputs.")
    for record_id, prediction in prediction_by_id.items():
        expected_input_hash = manifest_input_hash(input_by_id[record_id])
        if prediction.input_sha256 != expected_input_hash:
            raise ValueError(f"Prediction input fingerprint mismatch for {record_id}.")
        if prediction.predictor != manifest.predictor:
            raise ValueError(f"Prediction provider mismatch for {record_id}.")
        if prediction.predictor_version != manifest.predictor_version:
            raise ValueError(f"Prediction provider version mismatch for {record_id}.")
        if prediction.suite != label_by_id[record_id].suite:
            raise ValueError(f"Prediction and label suite mismatch for {record_id}.")

    suites = [
        _score_cfpb(predictions, labels),
        _score_fos(predictions, labels),
        _score_uci(predictions, labels),
    ]
    report = PublicBenchmarkReport(
        run_id=run_id,
        scored_at=(clock or _utc_now)(),
        predictor=manifest.predictor,
        predictor_version=manifest.predictor_version,
        source_manifest_sha256=manifest.source_manifest_sha256,
        prediction_manifest_sha256=sha256_file(manifest_path),
        label_snapshots=label_snapshots,
        suites=suites,
        integrity_checks=[
            "prediction_phase_used_input_files_only",
            "source_manifest_unchanged",
            "prepared_manifest_artifact_hashes_match",
            "input_artifact_hashes_unchanged",
            "prediction_artifact_hash_matches",
            "input_prediction_label_ids_aligned",
            "prediction_input_fingerprints_match",
            "suite_boundaries_preserved",
            "no_cross_suite_aggregate_score",
        ],
        permitted_claim=(
            "Evaluated through a recorded blind pipeline on real, de-identified public complaint "
            "decisions, public consumer complaint records, and real retail transaction data."
        ),
        limitations=[
            "The bundled predictor is a transparent deterministic baseline, not the production "
            "Decision Brief model.",
            "CFPB response categories describe company outcomes and are not fully inferable from "
            "complaint narratives alone.",
            "The selected FOS decisions are a small engineering sample, not a statistical sample "
            "or legal benchmark.",
            "UCI positive labels use a documented exact-match heuristic and are not customer "
            "support ground truth.",
            "The three source suites remain separate and do not constitute complete business "
            "cases.",
        ],
    )
    atomic_write_json(
        root,
        run_root / "report.json",
        report.model_dump(mode="json"),
    )
    atomic_write_bytes(
        root,
        run_root / "report.md",
        _render_markdown(report).encode("utf-8"),
    )
    return report


def manifest_input_hash(record: BenchmarkInputRecord) -> str:
    from app.evaluation.public_benchmark.baseline import input_fingerprint

    return input_fingerprint(record)


def _load_inputs(root: Path) -> tuple[list[BenchmarkInputRecord], list[InputSnapshot]]:
    records: list[BenchmarkInputRecord] = []
    snapshots: list[InputSnapshot] = []
    for suite in _SUITES:
        path = ensure_within(root, root / "prepared" / suite / "inputs.jsonl")
        if not path.is_file():
            raise ValueError(f"Prepared {suite} inputs are required.")
        suite_records = read_jsonl(path, BENCHMARK_INPUT_ADAPTER)
        if not suite_records or any(record.suite != suite for record in suite_records):
            raise ValueError(f"Prepared {suite} input boundary is invalid.")
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
    records.sort(key=lambda record: (_SUITE_ORDER[record.suite], record.record_id))
    return records, snapshots


def _load_labels(root: Path) -> tuple[list[BenchmarkLabelRecord], list[InputSnapshot]]:
    records: list[BenchmarkLabelRecord] = []
    snapshots: list[InputSnapshot] = []
    for suite in _SUITES:
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


def _score_cfpb(
    predictions: Sequence[BenchmarkPredictionRecord],
    labels: Sequence[BenchmarkLabelRecord],
) -> SuiteMetrics:
    predicted = {
        item.record_id: item for item in predictions if isinstance(item, CfpbPredictionRecord)
    }
    expected = [item for item in labels if isinstance(item, CfpbLabelRecord)]
    actual_values = [item.payload.company_response for item in expected]
    predicted_values = [predicted[item.record_id].payload.company_response for item in expected]
    timely_accuracy = _mean(
        [
            predicted[item.record_id].payload.timely_response == item.payload.timely_response
            for item in expected
        ]
    )
    return _suite_metrics(
        suite="cfpb",
        task="Predict public company response category from the complaint-side record.",
        expected=actual_values,
        predicted=predicted_values,
        labels=_CFPB_LABELS,
        secondary={"timely_response_accuracy": timely_accuracy},
        interpretation=(
            "This is a deliberately cheap input-only baseline. Response category is partly driven "
            "by company behavior after intake, so narrative-only accuracy is not a direct measure "
            "of Decision Brief quality."
        ),
    )


def _score_fos(
    predictions: Sequence[BenchmarkPredictionRecord],
    labels: Sequence[BenchmarkLabelRecord],
) -> SuiteMetrics:
    predicted = {
        item.record_id: item for item in predictions if isinstance(item, FosPredictionRecord)
    }
    expected = [item for item in labels if isinstance(item, FosLabelRecord)]
    return _suite_metrics(
        suite="fos",
        task="Predict final complaint disposition from the outcome-sanitized factual record.",
        expected=[item.payload.outcome for item in expected],
        predicted=[predicted[item.record_id].payload.outcome for item in expected],
        labels=_FOS_LABELS,
        secondary={},
        interpretation=(
            "The sample tests blind disposition reasoning after explicit outcome fragments are "
            "removed. Its size is suitable for engineering calibration only."
        ),
    )


def _score_uci(
    predictions: Sequence[BenchmarkPredictionRecord],
    labels: Sequence[BenchmarkLabelRecord],
) -> SuiteMetrics:
    predicted = {
        item.record_id: item for item in predictions if isinstance(item, UciPredictionRecord)
    }
    expected = [item for item in labels if isinstance(item, UciLabelRecord)]
    expected_values = [item.payload.relationship for item in expected]
    predicted_values = [predicted[item.record_id].payload.relationship for item in expected]
    positive = "candidate_cancellation_match"
    true_positive = sum(
        expected_value == positive and predicted_value == positive
        for expected_value, predicted_value in zip(expected_values, predicted_values, strict=True)
    )
    false_positive = sum(
        expected_value != positive and predicted_value == positive
        for expected_value, predicted_value in zip(expected_values, predicted_values, strict=True)
    )
    false_negative = sum(
        expected_value == positive and predicted_value != positive
        for expected_value, predicted_value in zip(expected_values, predicted_values, strict=True)
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
    return _suite_metrics(
        suite="uci",
        task="Link a cancellation row to its candidate original sale using explicit fields.",
        expected=expected_values,
        predicted=predicted_values,
        labels=_UCI_LABELS,
        secondary={
            "candidate_match_precision": precision,
            "candidate_match_recall": recall,
            "candidate_match_f1": positive_f1,
            "matched_invoice_accuracy": invoice_accuracy,
        },
        interpretation=(
            "This measures deterministic entity matching against the dataset builder's documented "
            "exact-match rule, not adjudication quality."
        ),
    )


def _suite_metrics(
    *,
    suite: SuiteName,
    task: str,
    expected: Sequence[str],
    predicted: Sequence[str],
    labels: Sequence[str],
    secondary: dict[str, float],
    interpretation: str,
) -> SuiteMetrics:
    if not expected or len(expected) != len(predicted):
        raise ValueError(f"{suite} scoring requires aligned, non-empty values.")
    confusion = {label: {predicted_label: 0 for predicted_label in labels} for label in labels}
    for expected_value, predicted_value in zip(expected, predicted, strict=True):
        if expected_value not in confusion or predicted_value not in confusion[expected_value]:
            raise ValueError(f"Unsupported {suite} score label.")
        confusion[expected_value][predicted_value] += 1
    f1_values: list[float] = []
    for label in labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[other][label] for other in labels if other != label)
        false_negative = sum(confusion[label][other] for other in labels if other != label)
        precision = _divide(true_positive, true_positive + false_positive)
        recall = _divide(true_positive, true_positive + false_negative)
        f1_values.append(_divide(2 * precision * recall, precision + recall))
    return SuiteMetrics(
        suite=suite,
        task=task,
        records=len(expected),
        accuracy=_mean(
            [
                expected_value == predicted_value
                for expected_value, predicted_value in zip(expected, predicted, strict=True)
            ]
        ),
        macro_f1=sum(f1_values) / len(f1_values),
        expected_distribution=dict(Counter(expected)),
        predicted_distribution=dict(Counter(predicted)),
        confusion_matrix=confusion,
        secondary_metrics=secondary,
        interpretation=interpretation,
    )


def _index_unique[T](records: Sequence[T], kind: str) -> dict[str, T]:
    indexed: dict[str, T] = {}
    for record in records:
        record_id = getattr(record, "record_id", None)
        if not isinstance(record_id, str):
            raise ValueError(f"Invalid {kind} record.")
        if record_id in indexed:
            raise ValueError(f"Duplicate {kind} record ID: {record_id}")
        indexed[record_id] = record
    return indexed


def _validate_artifact(path: Path, artifact: RunArtifact, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label.title()} artifact is missing.")
    if path.stat().st_size != artifact.bytes:
        raise ValueError(f"{label.title()} artifact byte count changed.")
    if sha256_file(path) != artifact.sha256:
        raise ValueError(f"{label.title()} artifact hash changed.")


def _run_root(root: Path, run_id: RunId) -> Path:
    return ensure_within(root, root / "runs" / run_id)


def _mean(values: Sequence[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _render_markdown(report: PublicBenchmarkReport) -> str:
    lines = [
        "# Public Benchmark Blind Run",
        "",
        f"- Run: `{report.run_id}`",
        f"- Predictor: `{report.predictor}` / `{report.predictor_version}`",
        f"- Scored at: `{report.scored_at.isoformat()}`",
        f"- Prediction manifest: `{report.prediction_manifest_sha256}`",
        "",
        "## Results",
        "",
        "| Suite | Records | Accuracy | Macro F1 |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| {suite.suite.upper()} | {suite.records} | {suite.accuracy:.3f} | {suite.macro_f1:.3f} |"
        for suite in report.suites
    )
    lines.extend(
        [
            "",
            "Scores are intentionally reported per suite. There is no cross-suite aggregate "
            "because the tasks have different semantics.",
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
