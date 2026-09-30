from hashlib import sha256
from pathlib import Path

from app.evaluation.case_resolution.models import (
    CaseResolutionBenchmarkInputSuite,
    CaseResolutionBenchmarkLabelSuite,
    CaseResolutionBenchmarkManifest,
    FrozenCaseResolutionBenchmark,
)


def load_frozen_case_resolution_inputs(
    root: Path,
) -> tuple[CaseResolutionBenchmarkManifest, CaseResolutionBenchmarkInputSuite]:
    manifest = CaseResolutionBenchmarkManifest.model_validate_json(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    inputs_bytes = (root / manifest.inputs_file).read_bytes()
    _require_hash("inputs", inputs_bytes, manifest.inputs_sha256)
    return manifest, CaseResolutionBenchmarkInputSuite.model_validate_json(inputs_bytes)


def load_frozen_case_resolution_benchmark(
    root: Path,
) -> FrozenCaseResolutionBenchmark:
    manifest = CaseResolutionBenchmarkManifest.model_validate_json(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    inputs_path = root / manifest.inputs_file
    labels_path = root / manifest.labels_file
    inputs_bytes = inputs_path.read_bytes()
    labels_bytes = labels_path.read_bytes()
    _require_hash("inputs", inputs_bytes, manifest.inputs_sha256)
    _require_hash("labels", labels_bytes, manifest.labels_sha256)
    inputs = CaseResolutionBenchmarkInputSuite.model_validate_json(inputs_bytes)
    labels = CaseResolutionBenchmarkLabelSuite.model_validate_json(labels_bytes)
    _require_matching_coverage(inputs, labels)
    _require_known_references(inputs, labels)
    return FrozenCaseResolutionBenchmark(
        manifest=manifest,
        inputs=inputs,
        labels=labels,
    )


def _require_hash(name: str, content: bytes, expected: str) -> None:
    observed = sha256(content).hexdigest()
    if observed != expected:
        raise ValueError(
            f"Frozen case-resolution {name} hash mismatch; "
            f"expected={expected}, observed={observed}."
        )


def _require_matching_coverage(
    inputs: CaseResolutionBenchmarkInputSuite,
    labels: CaseResolutionBenchmarkLabelSuite,
) -> None:
    input_ids = {case.case_id for case in inputs.cases}
    label_ids = {case.case_id for case in labels.cases}
    if input_ids != label_ids:
        raise ValueError(
            "Frozen case-resolution coverage mismatch; "
            f"missing_labels={sorted(input_ids - label_ids)}, "
            f"extra_labels={sorted(label_ids - input_ids)}."
        )


def _require_known_references(
    inputs: CaseResolutionBenchmarkInputSuite,
    labels: CaseResolutionBenchmarkLabelSuite,
) -> None:
    inputs_by_id = {case.case_id: case for case in inputs.cases}
    for label in labels.cases:
        case = inputs_by_id[label.case_id]
        evidence_ids = {item.public_id for item in case.available_evidence}
        unknown_evidence = sorted(set(label.required_evidence_ids) - evidence_ids)
        if unknown_evidence:
            raise ValueError(
                f"Gold label {label.case_id} references unavailable evidence: {unknown_evidence}."
            )
        policy_references = {
            (item.policy_public_id, item.version, item.clause_public_id)
            for item in case.available_policy_context
        }
        unknown_policies = sorted(
            (
                item.policy_public_id,
                item.version,
                item.clause_public_id,
            )
            for item in label.required_policy_references
            if (
                item.policy_public_id,
                item.version,
                item.clause_public_id,
            )
            not in policy_references
        )
        if unknown_policies:
            raise ValueError(
                f"Gold label {label.case_id} references unavailable policy clauses: "
                f"{unknown_policies}."
            )
