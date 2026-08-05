import json
from collections.abc import Sequence
from pathlib import Path

from app.evaluation.public_benchmark.models import (
    BENCHMARK_INPUT_ADAPTER,
    BENCHMARK_LABEL_ADAPTER,
    BenchmarkInputRecord,
    BenchmarkLabelRecord,
    FosInputRecord,
    PublicBenchmarkManifest,
    SourceRecord,
    SuiteName,
    UciLabelRecord,
    ValidationSummary,
)
from app.evaluation.public_benchmark.storage import ensure_within, read_jsonl, sha256_file
from app.evaluation.public_benchmark.transforms import find_fos_outcome_leakage

_SUITES: tuple[SuiteName, ...] = ("cfpb", "fos", "uci")


def validate_public_benchmark(
    data_root: Path,
    *,
    require_manifest: bool = True,
) -> ValidationSummary:
    root = data_root.resolve()
    input_records: list[BenchmarkInputRecord] = []
    label_records: list[BenchmarkLabelRecord] = []
    input_counts: dict[SuiteName, int] = {"cfpb": 0, "fos": 0, "uci": 0}
    label_counts: dict[SuiteName, int] = {"cfpb": 0, "fos": 0, "uci": 0}

    for suite in _SUITES:
        suite_root = ensure_within(root, root / "prepared" / suite)
        inputs_path = ensure_within(root, suite_root / "inputs.jsonl")
        labels_path = ensure_within(root, suite_root / "labels.jsonl")
        if not inputs_path.is_file() or not labels_path.is_file():
            raise ValueError(f"Prepared {suite} inputs and labels are required.")
        suite_inputs = read_jsonl(inputs_path, BENCHMARK_INPUT_ADAPTER)
        suite_labels = read_jsonl(labels_path, BENCHMARK_LABEL_ADAPTER)
        if not suite_inputs:
            raise ValueError(f"Prepared {suite} input set is empty.")
        if any(record.suite != suite for record in suite_inputs):
            raise ValueError(f"Prepared {suite} inputs contain a foreign suite.")
        if any(record.suite != suite for record in suite_labels):
            raise ValueError(f"Prepared {suite} labels contain a foreign suite.")
        input_records.extend(suite_inputs)
        label_records.extend(suite_labels)
        input_counts[suite] = len(suite_inputs)
        label_counts[suite] = len(suite_labels)

    input_by_id = _unique_records(input_records, record_kind="input")
    label_by_id = _unique_records(label_records, record_kind="label")
    if input_by_id.keys() != label_by_id.keys():
        missing_labels = sorted(input_by_id.keys() - label_by_id.keys())
        missing_inputs = sorted(label_by_id.keys() - input_by_id.keys())
        raise ValueError(
            f"Input/label ID mismatch; missing_labels={missing_labels}, "
            f"missing_inputs={missing_inputs}."
        )

    for record_id, input_record in input_by_id.items():
        label_record = label_by_id[record_id]
        if input_record.suite != label_record.suite:
            raise ValueError(f"Suite mismatch for {record_id}.")
        if input_record.source_record_id != label_record.source_record_id:
            raise ValueError(f"Source record mismatch for {record_id}.")
        if input_record.source_artifact_sha256 != label_record.source_artifact_sha256:
            raise ValueError(f"Source hash mismatch for {record_id}.")

    _validate_fos_leakage(input_records)
    _validate_uci_balance(label_records)
    _validate_source_separation(input_records)

    checks = [
        "suite_files_present",
        "schema_valid",
        "record_ids_unique",
        "inputs_and_labels_aligned",
        "source_metadata_aligned",
        "fos_outcome_leakage_absent",
        "uci_pair_labels_balanced",
        "source_suites_not_joined",
    ]
    summary = ValidationSummary(
        passed=True,
        input_records=input_counts,
        label_records=label_counts,
        checks=checks,
    )
    manifest_path = root / "manifest.json"
    if require_manifest:
        _validate_manifest(root, manifest_path, summary)
        summary.checks.append("manifest_hashes_match")
    return summary


def _unique_records(
    records: Sequence[SourceRecord],
    *,
    record_kind: str,
) -> dict[str, SourceRecord]:
    indexed: dict[str, SourceRecord] = {}
    for record in records:
        if record.record_id in indexed:
            raise ValueError(f"Duplicate {record_kind} record ID: {record.record_id}")
        indexed[record.record_id] = record
    return indexed


def _validate_fos_leakage(records: list[BenchmarkInputRecord]) -> None:
    for record in records:
        if not isinstance(record, FosInputRecord):
            continue
        leakage = find_fos_outcome_leakage(record.payload.case_text)
        if leakage:
            raise ValueError(f"FOS outcome leakage in {record.record_id}: {leakage}")


def _validate_uci_balance(records: list[BenchmarkLabelRecord]) -> None:
    uci_labels = [record for record in records if isinstance(record, UciLabelRecord)]
    matches = sum(
        record.payload.relationship == "candidate_cancellation_match" for record in uci_labels
    )
    unrelated = sum(record.payload.relationship == "unrelated_pair" for record in uci_labels)
    if matches == 0 or matches != unrelated:
        raise ValueError(
            f"UCI prepared labels must be balanced; matches={matches}, unrelated={unrelated}."
        )


def _validate_source_separation(records: list[BenchmarkInputRecord]) -> None:
    source_ids: dict[str, SuiteName] = {}
    for record in records:
        previous_suite = source_ids.get(record.source_record_id)
        if previous_suite is not None and previous_suite != record.suite:
            raise ValueError(
                f"Source record {record.source_record_id} is reused across "
                f"{previous_suite} and {record.suite}."
            )
        source_ids[record.source_record_id] = record.suite


def _validate_manifest(
    root: Path,
    manifest_path: Path,
    summary: ValidationSummary,
) -> None:
    if not manifest_path.is_file():
        raise ValueError("Public benchmark manifest is required.")
    manifest = PublicBenchmarkManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    if manifest.validation.input_records != summary.input_records:
        raise ValueError("Manifest input counts do not match prepared data.")
    if manifest.validation.label_records != summary.label_records:
        raise ValueError("Manifest label counts do not match prepared data.")
    for artifact in manifest.artifacts:
        path = ensure_within(root, root / artifact.path)
        if not path.is_file():
            raise ValueError(f"Manifest artifact is missing: {artifact.path}")
        if path.stat().st_size != artifact.bytes:
            raise ValueError(f"Manifest byte count changed: {artifact.path}")
        if sha256_file(path) != artifact.sha256:
            raise ValueError(f"Manifest hash changed: {artifact.path}")
        if artifact.records is not None:
            if artifact.kind == "raw":
                continue
            if _count_jsonl(path) != artifact.records:
                raise ValueError(f"Manifest record count changed: {artifact.path}")


def _count_jsonl(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                json.loads(line)
                count += 1
    return count
