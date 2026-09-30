import json
import shutil
from pathlib import Path

import pytest

from app.evaluation.case_resolution.generation import generate_deterministic_observation
from app.evaluation.case_resolution.models import BenchmarkCategory
from app.evaluation.case_resolution.reporting import _consistency
from app.evaluation.case_resolution.runner import (
    generate_observations,
    score_observations,
)
from app.evaluation.case_resolution.validation import (
    load_frozen_case_resolution_benchmark,
)

BENCHMARK_ROOT = (
    Path(__file__).resolve().parents[2] / "evaluations" / "case_resolution_v1"
)


def test_frozen_case_resolution_benchmark_is_valid_and_complete() -> None:
    benchmark = load_frozen_case_resolution_benchmark(BENCHMARK_ROOT)

    assert len(benchmark.inputs.cases) == 10
    assert len(benchmark.labels.cases) == 10
    assert benchmark.manifest.repeats_per_case == 2
    assert {
        category: sum(
            case.benchmark_category is category for case in benchmark.inputs.cases
        )
        for category in BenchmarkCategory
    } == {
        BenchmarkCategory.COMMON: 3,
        BenchmarkCategory.MISSING_INFORMATION: 2,
        BenchmarkCategory.CONFLICTING_EVIDENCE: 2,
        BenchmarkCategory.POLICY_HEAVY: 1,
        BenchmarkCategory.NOISY_EVIDENCE: 1,
        BenchmarkCategory.ADVERSARIAL_SAFETY: 1,
    }


def test_frozen_case_resolution_benchmark_rejects_tampered_inputs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case_resolution_v1"
    shutil.copytree(BENCHMARK_ROOT, root)
    payload = json.loads((root / "inputs.json").read_text(encoding="utf-8"))
    payload["cases"][0]["scenario"] = "Tampered after freeze."
    (root / "inputs.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="inputs hash mismatch"):
        load_frozen_case_resolution_benchmark(root)


def test_frozen_case_resolution_benchmark_has_separate_gold_labels() -> None:
    inputs = json.loads((BENCHMARK_ROOT / "inputs.json").read_text(encoding="utf-8"))

    serialized = json.dumps(inputs).lower()
    assert "expected_resolution" not in serialized
    assert "notes_for_grader" not in serialized
    assert "required_actions" not in serialized


def test_deterministic_generation_uses_production_langgraph_contract() -> None:
    benchmark = load_frozen_case_resolution_benchmark(BENCHMARK_ROOT)

    observation = generate_deterministic_observation(
        benchmark.inputs.cases[0],
        repeat_index=1,
    )

    assert observation.error_type is None
    assert observation.analysis is not None
    assert observation.analysis.policy_status.value == "relevant"
    assert observation.analysis.state.value == "ready_for_review"
    assert [action.type for action in observation.analysis.proposed_actions] == [
        "reverse_duplicate_charge"
    ]


def test_generate_then_score_keeps_observation_and_gold_phases_separate(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "case-resolution-results"

    observations = generate_observations(
        benchmark_root=BENCHMARK_ROOT,
        output_root=output_root,
        run_id="unit-case-001",
        case_ids=("CRV1-001",),
        repeats=1,
    )

    run_root = output_root / "runs" / "unit-case-001"
    assert len(observations.observations) == 1
    assert (run_root / "observations.json").is_file()
    assert not (run_root / "report.json").exists()

    report = score_observations(
        benchmark_root=BENCHMARK_ROOT,
        output_root=output_root,
        run_id="unit-case-001",
    )

    assert report.complete_run is False
    assert report.metrics.observation_count == 1
    assert report.metrics.schema_validity_rate == 1
    assert report.metrics.escalation_accuracy == 1
    assert report.metrics.risk_outcome_pass_rate == 1
    assert (run_root / "report.json").is_file()
    assert (run_root / "report.md").is_file()


def test_generation_rejects_more_than_two_repeats(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="between 1 and 2"):
        generate_observations(
            benchmark_root=BENCHMARK_ROOT,
            output_root=tmp_path / "case-resolution-results",
            run_id="invalid-three-repeat-run",
            case_ids=("CRV1-001",),
            repeats=3,
        )


def test_two_matching_repeats_report_full_consistency(tmp_path: Path) -> None:
    output_root = tmp_path / "case-resolution-results"

    generate_observations(
        benchmark_root=BENCHMARK_ROOT,
        output_root=output_root,
        run_id="two-repeat-consistency",
        case_ids=("CRV1-001",),
        repeats=2,
    )
    report = score_observations(
        benchmark_root=BENCHMARK_ROOT,
        output_root=output_root,
        run_id="two-repeat-consistency",
    )

    assert _consistency(report.grades, expected_repeats=2) == 1
