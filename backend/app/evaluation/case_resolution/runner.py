import re
from pathlib import Path

from app.evaluation.case_resolution.generation import generate_deterministic_observation
from app.evaluation.case_resolution.models import (
    CaseResolutionEvaluationReport,
    CaseResolutionObservationSuite,
)
from app.evaluation.case_resolution.reporting import build_report, render_markdown
from app.evaluation.case_resolution.scoring import score_observation
from app.evaluation.case_resolution.validation import (
    load_frozen_case_resolution_benchmark,
    load_frozen_case_resolution_inputs,
)
from app.evaluation.public_benchmark.storage import atomic_write_json

_RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def generate_observations(
    *,
    benchmark_root: Path,
    output_root: Path,
    run_id: str,
    case_ids: tuple[str, ...],
    repeats: int,
) -> CaseResolutionObservationSuite:
    _validate_run_id(run_id)
    if repeats < 1 or repeats > 2:
        raise ValueError("Repeats must be between 1 and 2.")
    manifest, inputs = load_frozen_case_resolution_inputs(benchmark_root)
    by_id = {case.case_id: case for case in inputs.cases}
    unknown = sorted(set(case_ids) - set(by_id))
    if unknown:
        raise ValueError(f"Unknown case IDs: {unknown}.")
    if not case_ids:
        raise ValueError("At least one case ID is required.")
    run_root = output_root / "runs" / run_id
    if run_root.exists():
        raise FileExistsError(f"Evaluation run already exists: {run_id}")
    run_root.mkdir(parents=True)
    observations = tuple(
        generate_deterministic_observation(by_id[case_id], repeat_index=repeat_index)
        for case_id in case_ids
        for repeat_index in range(1, repeats + 1)
    )
    suite = CaseResolutionObservationSuite(
        version="case-resolution-observation-v1",
        manifest_inputs_sha256=manifest.inputs_sha256,
        execution_mode="deterministic",
        observations=observations,
    )
    atomic_write_json(
        output_root,
        run_root / "contract.json",
        {
            "run_id": run_id,
            "execution_mode": "deterministic",
            "inputs_sha256": manifest.inputs_sha256,
            "case_ids": list(case_ids),
            "repeats": repeats,
        },
    )
    atomic_write_json(
        output_root,
        run_root / "observations.json",
        suite.model_dump(mode="json"),
    )
    return suite


def score_observations(
    *,
    benchmark_root: Path,
    output_root: Path,
    run_id: str,
) -> CaseResolutionEvaluationReport:
    _validate_run_id(run_id)
    benchmark = load_frozen_case_resolution_benchmark(benchmark_root)
    run_root = output_root / "runs" / run_id
    observations = CaseResolutionObservationSuite.model_validate_json(
        (run_root / "observations.json").read_text(encoding="utf-8")
    )
    if observations.manifest_inputs_sha256 != benchmark.manifest.inputs_sha256:
        raise ValueError("Observation input hash does not match the frozen benchmark.")
    labels = {item.case_id: item for item in benchmark.labels.cases}
    grades = tuple(
        score_observation(item, labels[item.case_id]) for item in observations.observations
    )
    report = build_report(
        run_id=run_id,
        manifest=benchmark.manifest,
        grades=grades,
    )
    atomic_write_json(
        output_root,
        run_root / "report.json",
        report.model_dump(mode="json"),
    )
    (run_root / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def _validate_run_id(run_id: str) -> None:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Run ID must use lowercase letters, digits, dots, dashes, or underscores.")
