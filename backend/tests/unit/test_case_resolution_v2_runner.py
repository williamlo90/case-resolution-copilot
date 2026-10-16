from pathlib import Path
from shutil import copytree
from typing import Any

import pytest

from app.evaluation.case_resolution_v2.corpus import ROOT, inputs, validate_corpus
from app.evaluation.case_resolution_v2.models import Observation, Scenario
from app.evaluation.case_resolution_v2.runner import (
    capture_one,
    declare_run,
    score_run,
    seal_observations,
)
from app.evaluation.case_resolution_v2.storage import write_new
from tests.unit.test_case_resolution_v2_scoring import example

CONFIG = dict(
    model_version="fixture",
    prompt_version="fixture",
    runtime_adapter_version="fixture-v1",
    policy_snapshot_sha256="b" * 64,
    environment="unit-test",
    seed=1,
)


def test_authored_corpus_counts_and_family_isolation() -> None:
    assert validate_corpus() == {"development": 24, "regression": 3, "holdout": 40, "time_study": 0}


def test_runtime_input_loader_never_reads_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_text

    def guarded(path: Path, *args: Any, **kwargs: Any) -> str:
        assert "labels" not in path.parts
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    _, cases = inputs(ROOT, "development")
    assert len(cases) == 24


def test_capture_then_seal_then_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, payload = example()
    observation = Observation.model_validate(payload)
    original = Path.read_text

    def guarded(path: Path, *args: Any, **kwargs: Any) -> str:
        assert "labels" not in path.parts
        return original(path, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(Path, "read_text", guarded)
        capture_one(
            root=ROOT,
            split="development",
            case_id=observation.case_id,
            output=tmp_path / "run",
            adapter=lambda _: observation,
            execution_profile="evaluator_contract_test",
            product_revision="a" * 40,
            config=CONFIG,
        )
    with pytest.raises(FileNotFoundError):
        score_run(root=ROOT, split="development", output=tmp_path / "run")
    seal_observations(
        root=ROOT,
        split="development",
        output=tmp_path / "run",
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    report = score_run(root=ROOT, split="development", output=tmp_path / "run")
    assert report["correct_completion"]["numerator"] == 1
    assert report["run_identity"]["execution_profile"] == "evaluator_contract_test"
    with pytest.raises(FileExistsError):
        score_run(root=ROOT, split="development", output=tmp_path / "run")


def test_failures_and_missing_are_in_scheduled_denominator(tmp_path: Path) -> None:
    declare_run(
        root=ROOT,
        split="development",
        output=tmp_path,
        case_ids=["V2-DEV-001", "V2-DEV-002", "V2-DEV-003"],
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    write_new(
        tmp_path / "V2-DEV-001.json",
        {"capture_error": "TimeoutError", "capture_status": "provider_failure"},
    )
    write_new(tmp_path / "V2-DEV-002.json", {"malformed": "response"})
    seal_observations(
        root=ROOT,
        split="development",
        output=tmp_path,
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    report = score_run(root=ROOT, split="development", output=tmp_path)
    assert report["scheduled"] == report["scored"] == 3
    assert report["missing"] == report["invalid"] == report["provider_failures"] == 1
    assert report["correct_completion"]["denominator"] == 3
    assert report["correct_completion"]["numerator"] == 0


def test_observation_tampering_rejected_before_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declare_run(
        root=ROOT,
        split="development",
        output=tmp_path,
        case_ids=["V2-DEV-001"],
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    seal_observations(
        root=ROOT,
        split="development",
        output=tmp_path,
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    write_new(tmp_path / "V2-DEV-001.json", {"late": "observation"})
    with pytest.raises(ValueError, match="Observation changed"):
        score_run(root=ROOT, split="development", output=tmp_path)


def test_input_and_label_tampering_rejected(tmp_path: Path) -> None:
    copytree(ROOT, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "development" / "inputs" / "V2-DEV-001.json"
    path.write_text(
        path.read_text()
        .replace("same immutable owner", "different owner")
        .replace("correct_billing_address", "wrong_action")
        .replace("passed", "failed")
    )
    with pytest.raises(ValueError, match="Input identity/hash"):
        validate_corpus(tmp_path)


def test_holdout_capture_is_disabled_locally(tmp_path: Path) -> None:
    def must_not_run(_: Scenario) -> Observation:
        raise AssertionError("Holdout adapter must not be invoked")

    with pytest.raises(ValueError, match="restricted"):
        capture_one(
            root=ROOT,
            split="holdout",
            case_id="V2-HLD-001",
            output=tmp_path / "run",
            adapter=must_not_run,
            execution_profile="evaluator_contract_test",
            product_revision="a" * 40,
            config=CONFIG,
        )


def test_zero_denominator_is_unavailable() -> None:
    from app.evaluation.case_resolution_v2.runner import _rate

    assert _rate(0, 0)["value"] is None
    assert _rate(0, 0)["wilson_95"] is None


def test_label_hash_tampering_is_rejected(tmp_path: Path) -> None:
    copytree(ROOT, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "development" / "labels" / "V2-DEV-001.json"
    path.write_text(path.read_text().replace('"supervisor_approval"', '"skip_approval"'))
    with pytest.raises(ValueError, match="Label identity/hash"):
        validate_corpus(tmp_path)


def test_holdout_partial_schedule_and_debug_profile_are_rejected(tmp_path: Path) -> None:
    write_new(
        tmp_path / "partial" / "schedule.json", {"split": "holdout", "case_ids": ["V2-HLD-001"]}
    )
    with pytest.raises(ValueError, match="every primary"):
        seal_observations(
            root=ROOT,
            split="holdout",
            output=tmp_path / "partial",
            execution_profile="provider_product",
            product_revision="a" * 40,
            config=CONFIG,
        )
    spec, _ = inputs(ROOT, "holdout")
    write_new(
        tmp_path / "debug" / "schedule.json",
        {"split": "holdout", "case_ids": [e.case_id for e in spec.entries]},
    )
    with pytest.raises(ValueError, match="debugging"):
        seal_observations(
            root=ROOT,
            split="holdout",
            output=tmp_path / "debug",
            execution_profile="evaluator_contract_test",
            product_revision="a" * 40,
            config=CONFIG,
        )


def test_runtime_failure_capture_redacts_exception_and_keeps_denominator(tmp_path: Path) -> None:
    def failing(_: Scenario) -> Observation:
        raise TimeoutError("secret-credential-and-customer-payload")

    run = tmp_path / "run"
    capture_one(
        root=ROOT,
        split="development",
        case_id="V2-DEV-001",
        output=run,
        adapter=failing,
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    assert "secret" not in (run / "V2-DEV-001.json").read_text()
    seal_observations(
        root=ROOT,
        split="development",
        output=run,
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    report = score_run(root=ROOT, split="development", output=run)
    assert report["provider_failures"] == report["scheduled"] == 1
    assert report["eligible_automation_coverage"]["value"] is None


def test_changed_evaluator_cannot_score_old_observation_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    declare_run(
        root=ROOT,
        split="development",
        output=tmp_path,
        case_ids=["V2-DEV-001"],
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    seal_observations(
        root=ROOT,
        split="development",
        output=tmp_path,
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    monkeypatch.setattr("app.evaluation.case_resolution_v2.runner.code_identity", lambda: "0" * 64)
    with pytest.raises(ValueError, match="Scorer/split identity"):
        score_run(root=ROOT, split="development", output=tmp_path)


def test_config_is_declared_before_adapter_and_cannot_change(tmp_path: Path) -> None:
    _, _, payload = example()

    def adapter(_: Scenario) -> Observation:
        assert (tmp_path / "run" / "run-contract.json").exists()
        return Observation.model_validate(payload)

    capture_one(
        root=ROOT,
        split="development",
        case_id="V2-DEV-002",
        output=tmp_path / "run",
        adapter=adapter,
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    with pytest.raises(ValueError, match="configuration changed"):
        seal_observations(
            root=ROOT,
            split="development",
            output=tmp_path / "run",
            execution_profile="evaluator_contract_test",
            product_revision="a" * 40,
            config={**CONFIG, "seed": 2},
        )


@pytest.mark.parametrize("body", ["{broken", "null"])
def test_malformed_json_still_counts_as_attempted_invalid(tmp_path: Path, body: str) -> None:
    declare_run(
        root=ROOT,
        split="development",
        output=tmp_path,
        case_ids=["V2-DEV-001"],
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    (tmp_path / "V2-DEV-001.json").write_text(body)
    seal_observations(
        root=ROOT,
        split="development",
        output=tmp_path,
        execution_profile="evaluator_contract_test",
        product_revision="a" * 40,
        config=CONFIG,
    )
    report = score_run(root=ROOT, split="development", output=tmp_path)
    assert report["attempted"] == report["invalid"] == report["scheduled"] == 1
    assert report["missing"] == 0
