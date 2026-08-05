from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.evaluation.public_benchmark.ai_models import (
    AI_PREDICTION_ADAPTER,
    AICfpbPredictionPayload,
    AICfpbPredictionRecord,
    AIEvaluationContract,
    AIFosPredictionPayload,
    AIFosPredictionRecord,
    AIPredictionManifest,
    AIPredictionProgress,
    AIPredictionRecord,
    AIUciPredictionPayload,
    AIUciPredictionRecord,
)
from app.evaluation.public_benchmark.ai_predictor import (
    AI_PUBLIC_BENCHMARK_PROMPT_VERSION,
    CfpbPublicAssessment,
    FosPublicAssessment,
    ProviderErrorCategory,
    PublicEvidenceModelError,
    PublicEvidenceResult,
    public_prompt_sha256,
)
from app.evaluation.public_benchmark.baseline import (
    BASELINE_NAME,
    BASELINE_VERSION,
    DeterministicPublicBaseline,
    input_fingerprint,
)
from app.evaluation.public_benchmark.file_locking import exclusive_run_lock
from app.evaluation.public_benchmark.models import (
    BENCHMARK_INPUT_ADAPTER,
    BenchmarkInputRecord,
    CfpbInputRecord,
    FosInputRecord,
    SuiteName,
    UciInputRecord,
)
from app.evaluation.public_benchmark.predictions import (
    InputSnapshot,
    RunArtifact,
    UciPredictionRecord,
)
from app.evaluation.public_benchmark.storage import (
    atomic_write_json,
    ensure_within,
    read_jsonl,
    relative_manifest_path,
    sha256_file,
    write_jsonl,
)

AI_PREDICTOR_NAME = "openai-public-evidence-evaluator"
DEFAULT_AI_RUN_ID = "openai-public-evidence-v2"
DEFAULT_MODEL_CALL_BUDGET = 46
DEFAULT_MAX_OUTPUT_TOKENS = 700
DEFAULT_TIMEOUT_SECONDS = 60.0
SUITES: tuple[SuiteName, ...] = ("cfpb", "fos", "uci")
_SUITE_ORDER = {suite: index for index, suite in enumerate(SUITES)}
_MODEL_SUITE_ORDER = {"fos": 0, "cfpb": 1}


class PublicEvidenceGateway(Protocol):
    provider_name: str
    model_version: str
    timeout_seconds: float
    max_output_tokens: int

    def predict(
        self,
        record: CfpbInputRecord | FosInputRecord,
    ) -> PublicEvidenceResult: ...


def generate_ai_predictions(
    data_root: Path,
    *,
    gateway: PublicEvidenceGateway,
    run_id: str = DEFAULT_AI_RUN_ID,
    model_call_budget: int = DEFAULT_MODEL_CALL_BUDGET,
    clock: Callable[[], datetime] | None = None,
) -> AIPredictionManifest:
    from app.evaluation.public_benchmark.ai_models import AI_RUN_ID_ADAPTER

    validated_run_id = AI_RUN_ID_ADAPTER.validate_python(run_id)
    root = data_root.resolve()
    run_root = run_root_for(root, validated_run_id)
    with exclusive_run_lock(run_root / "prediction.lock"):
        return _generate_ai_predictions_unlocked(
            data_root,
            gateway=gateway,
            run_id=validated_run_id,
            model_call_budget=model_call_budget,
            clock=clock,
        )


def _generate_ai_predictions_unlocked(
    data_root: Path,
    *,
    gateway: PublicEvidenceGateway,
    run_id: str,
    model_call_budget: int,
    clock: Callable[[], datetime] | None,
) -> AIPredictionManifest:
    from app.evaluation.public_benchmark.ai_models import AI_RUN_ID_ADAPTER

    validated_run_id = AI_RUN_ID_ADAPTER.validate_python(run_id)
    if not 1 <= model_call_budget <= DEFAULT_MODEL_CALL_BUDGET:
        raise ValueError("AI benchmark model-call budget must be between 1 and 46.")
    root = data_root.resolve()
    source_manifest = ensure_within(root, root / "manifest.json")
    if not source_manifest.is_file():
        raise ValueError("Prepared benchmark manifest is required before prediction.")
    inputs, snapshots = load_inputs(root)
    model_inputs = [
        record for record in inputs if isinstance(record, (CfpbInputRecord, FosInputRecord))
    ]
    if len(model_inputs) > model_call_budget:
        raise ValueError(
            f"Model-call budget {model_call_budget} cannot cover {len(model_inputs)} records."
        )
    run_root = run_root_for(root, validated_run_id)
    now = clock or utc_now
    contract = _load_or_freeze_contract(
        root=root,
        run_root=run_root,
        run_id=validated_run_id,
        gateway=gateway,
        source_manifest=source_manifest,
        snapshots=snapshots,
        model_call_budget=model_call_budget,
        frozen_at=now(),
    )
    contract_path = run_root / "contract.json"
    contract_sha256 = sha256_file(contract_path)
    by_id = index_unique(inputs, "input")
    partial_path = run_root / "predictions.partial.jsonl"
    predictions = read_jsonl(partial_path, AI_PREDICTION_ADAPTER) if partial_path.is_file() else []
    prediction_by_id = index_unique(predictions, "prediction")
    _validate_resumed_predictions(
        prediction_by_id=prediction_by_id,
        input_by_id=by_id,
        contract=contract,
    )
    progress = _load_or_initialize_progress(
        root=root,
        run_root=run_root,
        run_id=validated_run_id,
        contract_sha256=contract_sha256,
        prediction_ids=set(prediction_by_id),
        updated_at=now(),
    )
    if progress.active_record_id and progress.active_record_id not in prediction_by_id:
        interrupted = by_id.get(progress.active_record_id)
        if not isinstance(interrupted, (CfpbInputRecord, FosInputRecord)):
            raise ValueError("Interrupted progress references an invalid model record.")
        prediction_by_id[interrupted.record_id] = _safe_failure_prediction(
            interrupted,
            "interrupted",
            contract,
        )
        _checkpoint_predictions(root, partial_path, prediction_by_id.values())
        errors = dict(progress.provider_errors)
        errors["interrupted"] = errors.get("interrupted", 0) + 1
        progress = progress.model_copy(
            update={
                "completed_record_ids": sorted(prediction_by_id),
                "active_record_id": None,
                "provider_errors": errors,
                "updated_at": now(),
            }
        )
        _write_progress(root, run_root, progress)

    baseline = DeterministicPublicBaseline()
    for record in inputs:
        if not isinstance(record, UciInputRecord) or record.record_id in prediction_by_id:
            continue
        prediction = _uci_prediction(record, baseline, contract.prompt_sha256)
        prediction_by_id[record.record_id] = prediction
    _checkpoint_predictions(root, partial_path, prediction_by_id.values())
    progress = progress.model_copy(
        update={
            "completed_record_ids": sorted(prediction_by_id),
            "updated_at": now(),
            "active_record_id": None,
        }
    )
    _write_progress(root, run_root, progress)

    ordered_model_inputs = sorted(
        model_inputs,
        key=lambda record: (_MODEL_SUITE_ORDER[record.suite], record.record_id),
    )
    consecutive_errors = 0
    for record in ordered_model_inputs:
        if record.record_id in prediction_by_id:
            continue
        if progress.calls_started >= contract.model_call_budget:
            raise ValueError("AI benchmark exhausted its frozen model-call budget.")
        progress = progress.model_copy(
            update={
                "calls_started": progress.calls_started + 1,
                "active_record_id": record.record_id,
                "updated_at": now(),
            }
        )
        _write_progress(root, run_root, progress)
        error_category: ProviderErrorCategory | None = None
        try:
            result = gateway.predict(record)
            model_prediction = _model_prediction(record, result, contract)
            consecutive_errors = 0
        except PublicEvidenceModelError as exc:
            error_category = exc.category
            model_prediction = _safe_failure_prediction(record, exc.category, contract)
            consecutive_errors += 1
        prediction_by_id[record.record_id] = model_prediction
        _checkpoint_predictions(root, partial_path, prediction_by_id.values())
        errors = dict(progress.provider_errors)
        if error_category is not None:
            errors[error_category] = errors.get(error_category, 0) + 1
        progress = progress.model_copy(
            update={
                "completed_record_ids": sorted(prediction_by_id),
                "active_record_id": None,
                "provider_errors": errors,
                "updated_at": now(),
            }
        )
        _write_progress(root, run_root, progress)
        if error_category in {"authentication", "model_access"}:
            raise RuntimeError(
                f"AI benchmark stopped on provider configuration error: {error_category}."
            )
        if consecutive_errors >= 2:
            raise RuntimeError("AI benchmark stopped after two consecutive provider failures.")

    if prediction_by_id.keys() != by_id.keys():
        missing = sorted(by_id.keys() - prediction_by_id.keys())
        raise ValueError(f"AI benchmark predictions are incomplete: {missing[:3]}")
    predictions_path = run_root / "predictions.jsonl"
    count = write_jsonl(
        root,
        predictions_path,
        _sorted_predictions(prediction_by_id.values()),
    )
    artifact = RunArtifact(
        path=relative_manifest_path(root, predictions_path),
        sha256=sha256_file(predictions_path),
        bytes=predictions_path.stat().st_size,
        records=count,
    )
    model_predictions = [
        item
        for item in prediction_by_id.values()
        if isinstance(item, (AICfpbPredictionRecord, AIFosPredictionRecord))
    ]
    manifest = AIPredictionManifest(
        run_id=validated_run_id,
        completed_at=now(),
        predictor=contract.predictor,
        predictor_version=contract.predictor_version,
        model=contract.model,
        prompt_sha256=contract.prompt_sha256,
        contract_sha256=contract_sha256,
        source_manifest_sha256=contract.source_manifest_sha256,
        input_snapshots=contract.input_snapshots,
        predictions=artifact,
        model_calls_started=progress.calls_started,
        input_tokens=sum(item.payload.input_tokens for item in model_predictions),
        output_tokens=sum(item.payload.output_tokens for item in model_predictions),
    )
    atomic_write_json(
        root,
        run_root / "prediction-manifest.json",
        manifest.model_dump(mode="json"),
    )
    return manifest


def load_inputs(
    root: Path,
) -> tuple[list[BenchmarkInputRecord], list[InputSnapshot]]:
    records: list[BenchmarkInputRecord] = []
    snapshots: list[InputSnapshot] = []
    for suite in SUITES:
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


def index_unique[T](records: Sequence[T], kind: str) -> dict[str, T]:
    indexed: dict[str, T] = {}
    for record in records:
        record_id = getattr(record, "record_id", None)
        if not isinstance(record_id, str):
            raise ValueError(f"Invalid {kind} record.")
        if record_id in indexed:
            raise ValueError(f"Duplicate {kind} record ID: {record_id}")
        indexed[record_id] = record
    return indexed


def quote_is_supported(quote: str, input_text: str) -> bool:
    candidate = quote.strip()
    quote_pairs = {('"', '"'), ("'", "'"), ("\u201c", "\u201d"), ("\u2018", "\u2019")}
    while len(candidate) >= 2 and (candidate[0], candidate[-1]) in quote_pairs:
        candidate = candidate[1:-1].strip()
    normalized_quote = " ".join(candidate.casefold().split())
    normalized_input = " ".join(input_text.casefold().split())
    return bool(normalized_quote) and normalized_quote in normalized_input


def evidence_text(record: CfpbInputRecord | FosInputRecord) -> str:
    if isinstance(record, FosInputRecord):
        return record.payload.case_text
    return " ".join(
        str(value) for value in record.payload.model_dump(mode="python", exclude_none=True).values()
    )


def run_root_for(root: Path, run_id: str) -> Path:
    return ensure_within(root, root / "runs" / run_id)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _load_or_freeze_contract(
    *,
    root: Path,
    run_root: Path,
    run_id: str,
    gateway: PublicEvidenceGateway,
    source_manifest: Path,
    snapshots: list[InputSnapshot],
    model_call_budget: int,
    frozen_at: datetime,
) -> AIEvaluationContract:
    contract_path = ensure_within(root, run_root / "contract.json")
    existing = (
        AIEvaluationContract.model_validate_json(contract_path.read_text(encoding="utf-8"))
        if contract_path.is_file()
        else None
    )
    contract = AIEvaluationContract(
        run_id=run_id,
        frozen_at=existing.frozen_at if existing else frozen_at,
        predictor_version=_predictor_version(gateway.model_version),
        model=gateway.model_version,
        prompt_version=AI_PUBLIC_BENCHMARK_PROMPT_VERSION,
        prompt_sha256=public_prompt_sha256(),
        source_manifest_sha256=sha256_file(source_manifest),
        input_snapshots=snapshots,
        task_order=["fos", "cfpb"],
        model_call_budget=model_call_budget,
        max_output_tokens=gateway.max_output_tokens,
        timeout_seconds=gateway.timeout_seconds,
    )
    if existing is not None:
        if existing != contract:
            raise ValueError("Frozen AI evaluation contract does not match this invocation.")
        return existing
    atomic_write_json(root, contract_path, contract.model_dump(mode="json"))
    return contract


def _load_or_initialize_progress(
    *,
    root: Path,
    run_root: Path,
    run_id: str,
    contract_sha256: str,
    prediction_ids: set[str],
    updated_at: datetime,
) -> AIPredictionProgress:
    path = ensure_within(root, run_root / "progress.json")
    if path.is_file():
        progress = AIPredictionProgress.model_validate_json(path.read_text(encoding="utf-8"))
        if progress.run_id != run_id or progress.contract_sha256 != contract_sha256:
            raise ValueError("AI benchmark progress does not match the frozen contract.")
        if not set(progress.completed_record_ids).issubset(prediction_ids):
            raise ValueError("AI benchmark progress references an uncheckpointed prediction.")
        return progress
    progress = AIPredictionProgress(
        run_id=run_id,
        contract_sha256=contract_sha256,
        updated_at=updated_at,
        calls_started=0,
        completed_record_ids=sorted(prediction_ids),
    )
    _write_progress(root, run_root, progress)
    return progress


def _model_prediction(
    record: CfpbInputRecord | FosInputRecord,
    result: PublicEvidenceResult,
    contract: AIEvaluationContract,
) -> AICfpbPredictionRecord | AIFosPredictionRecord:
    input_text = evidence_text(record)
    assessment = result.assessment
    unsupported = [
        quote for quote in assessment.evidence_quotes if not quote_is_supported(quote, input_text)
    ]
    metadata = {
        "confidence": assessment.confidence,
        "evidence_quotes": assessment.evidence_quotes,
        "unsupported_evidence_quotes": unsupported,
        "uncertainty": assessment.uncertainty,
        "schema_valid": True,
        "review_required": assessment.review_required,
        "action_status": assessment.action_status,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
    }
    common = {
        "record_id": record.record_id,
        "input_sha256": input_fingerprint(record),
        "predictor": contract.predictor,
        "predictor_version": contract.predictor_version,
        "prompt_sha256": contract.prompt_sha256,
    }
    if isinstance(record, CfpbInputRecord) and isinstance(assessment, CfpbPublicAssessment):
        return AICfpbPredictionRecord(
            **common,
            payload=AICfpbPredictionPayload(
                company_response=assessment.company_response,
                **metadata,
            ),
        )
    if isinstance(record, FosInputRecord) and isinstance(assessment, FosPublicAssessment):
        return AIFosPredictionRecord(
            **common,
            payload=AIFosPredictionPayload(
                outcome=assessment.outcome,
                **metadata,
            ),
        )
    raise ValueError("Model assessment type does not match its benchmark suite.")


def _safe_failure_prediction(
    record: CfpbInputRecord | FosInputRecord,
    category: ProviderErrorCategory,
    contract: AIEvaluationContract,
) -> AICfpbPredictionRecord | AIFosPredictionRecord:
    metadata = {
        "confidence": "low",
        "evidence_quotes": [],
        "unsupported_evidence_quotes": [],
        "uncertainty": "No valid structured model result was available; safe abstention recorded.",
        "schema_valid": False,
        "review_required": True,
        "action_status": "analysis_only",
        "provider_error_category": category,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    common = {
        "record_id": record.record_id,
        "input_sha256": input_fingerprint(record),
        "predictor": contract.predictor,
        "predictor_version": contract.predictor_version,
        "prompt_sha256": contract.prompt_sha256,
    }
    if isinstance(record, CfpbInputRecord):
        return AICfpbPredictionRecord(
            **common,
            payload=AICfpbPredictionPayload(company_response="abstain", **metadata),
        )
    return AIFosPredictionRecord(
        **common,
        payload=AIFosPredictionPayload(outcome="abstain", **metadata),
    )


def _uci_prediction(
    record: UciInputRecord,
    baseline: DeterministicPublicBaseline,
    prompt_sha256: str,
) -> AIUciPredictionRecord:
    predicted = baseline.predict(record)
    if not isinstance(predicted, UciPredictionRecord):
        raise TypeError("Deterministic UCI predictor returned the wrong record type.")
    return AIUciPredictionRecord(
        record_id=record.record_id,
        input_sha256=predicted.input_sha256,
        predictor=BASELINE_NAME,
        predictor_version=BASELINE_VERSION,
        prompt_sha256=prompt_sha256,
        payload=AIUciPredictionPayload(
            relationship=predicted.payload.relationship,
            expected_original_invoice=predicted.payload.expected_original_invoice,
            rationale_signals=predicted.payload.rationale_signals,
        ),
    )


def _validate_resumed_predictions(
    *,
    prediction_by_id: dict[str, AIPredictionRecord],
    input_by_id: dict[str, BenchmarkInputRecord],
    contract: AIEvaluationContract,
) -> None:
    for record_id, prediction in prediction_by_id.items():
        if record_id not in input_by_id:
            raise ValueError(f"Checkpoint contains unknown prediction ID: {record_id}")
        record = input_by_id[record_id]
        if prediction.input_sha256 != input_fingerprint(record):
            raise ValueError(f"Checkpoint input fingerprint mismatch for {record_id}.")
        if prediction.prompt_sha256 != contract.prompt_sha256:
            raise ValueError(f"Checkpoint prompt fingerprint mismatch for {record_id}.")
        if prediction.suite != record.suite:
            raise ValueError(f"Checkpoint suite mismatch for {record_id}.")
        if prediction.suite == "uci":
            if (
                prediction.predictor != BASELINE_NAME
                or prediction.predictor_version != BASELINE_VERSION
            ):
                raise ValueError(f"Checkpoint deterministic predictor mismatch for {record_id}.")
        elif (
            prediction.predictor != contract.predictor
            or prediction.predictor_version != contract.predictor_version
        ):
            raise ValueError(f"Checkpoint model predictor mismatch for {record_id}.")


def _checkpoint_predictions(
    root: Path,
    path: Path,
    predictions: Iterable[AIPredictionRecord],
) -> None:
    write_jsonl(root, path, _sorted_predictions(predictions))


def _sorted_predictions(
    predictions: Iterable[AIPredictionRecord],
) -> list[AIPredictionRecord]:
    return sorted(
        predictions,
        key=lambda item: (_SUITE_ORDER[item.suite], item.record_id),
    )


def _write_progress(
    root: Path,
    run_root: Path,
    progress: AIPredictionProgress,
) -> None:
    atomic_write_json(
        root,
        run_root / "progress.json",
        progress.model_dump(mode="json"),
    )


def _predictor_version(model: str) -> str:
    value = f"{model}/{AI_PUBLIC_BENCHMARK_PROMPT_VERSION}"
    if len(value) > 100:
        raise ValueError("Model and prompt version exceed the predictor-version limit.")
    return value
