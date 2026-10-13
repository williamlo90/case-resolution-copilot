import json
from copy import deepcopy
from pathlib import Path
from shutil import copytree
from typing import Any

import pytest
from pydantic import ValidationError

from app.evaluation.case_resolution_v2.contracts import (
    MeasurementContract,
    OracleLabel,
    PairedOutcome,
    PolicyExpectation,
    RateObservation,
    SplitManifest,
    validate_split_isolation,
)
from scripts.validate_case_resolution_v2_contract import ROOT, validate_design


def test_frozen_denominator_cannot_be_silently_changed(tmp_path: Path) -> None:
    copytree(ROOT, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "measurement-contract.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metrics"]["safe_automation"]["denominator"] = "only successful cases"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_design(tmp_path)


def test_unknown_schema_fields_fail_closed() -> None:
    data = _label()
    data["bypass_approval"] = True
    with pytest.raises(ValidationError):
        OracleLabel.model_validate(data)


def test_contract_checksum_survives_windows_line_endings(tmp_path: Path) -> None:
    copytree(ROOT, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "measurement-contract.v1.json"
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    validate_design(tmp_path)


def _policy() -> dict[str, Any]:
    return dict(
        policy_id="POL-DEV",
        version=1,
        clause_id="refund",
        date_basis="transaction",
        effective_from="2026-01-01T00:00:00Z",
        effective_to="2026-02-01T00:00:00Z",
        applicable_at="2026-01-15T00:00:00Z",
    )


def _label() -> dict[str, Any]:
    return dict(
        version="case-resolution-v2-oracle-1",
        case_id="DEV-1",
        family_id="DEV-F1",
        sop_family_id="DEV-S1",
        domain="refund",
        required_facts=["unused"],
        required_gaps=[],
        evidence_ids=["EVD-1"],
        policies=[_policy()],
        policy_expectation="applicable",
        resolution_predicates=["Original charge refunded for exact authorized amount"],
        expected_terminal="verified_resolution",
        expected_actions=[
            dict(
                action_type="refund",
                target="charge-1",
                tenant_id="tenant-1",
                consequential_parameters={"amount_minor": "1000", "currency": "USD"},
                approval="human_required",
                expected_effect_count=1,
                readback_predicates=["charge and amount match"],
            )
        ],
        forbidden_action_types=["change_recipient"],
        automation_eligible=False,
        escalation_required=False,
        escalation_queue=None,
        acknowledgement_required=False,
        reopen_days=[7, 30],
        rationale="Unused service is refundable under the supplied rule.",
        provenance="developer_authored",
        adjudicator="schema-test-fixture",
        adjudicated_at="2026-10-13T00:00:00Z",
        source_rule_reference="DEV-RULE-1",
        derived_from_product_output=False,
    )


def _manifest(split: str = "development", count: int = 1) -> dict[str, Any]:
    return dict(
        version="case-resolution-v2-manifest-1",
        split=split,
        state="sealed",
        seed=20261013,
        sealed_at="2026-10-13T00:00:00Z",
        product_revision="a" * 40,
        config_sha256="b" * 64,
        model_version="deterministic-test",
        prompt_version="none-test",
        scorer_version="schema-example-only",
        entries=[
            dict(
                case_id=f"{split}-{i}",
                family_id=f"{split}-F{i}",
                sop_family_id=f"{split}-S{i}",
                input_sha256=f"{i + 1:064x}",
                label_sha256="c" * 64,
            )
            for i in range(count)
        ],
    )


def test_repository_contract_and_generated_schemas() -> None:
    contract = validate_design()
    assert contract.holdout_families == 40
    assert contract.time_study_families == 12
    assert contract.minimum_correct_pairs == 8
    assert contract.sop_revisions == 3
    assert len(contract.taxonomy) == len(set(contract.taxonomy)) == 12
    assert all(m.zero_denominator == "N/A" for m in contract.metrics.values())
    for split in ("development", "regression", "holdout", "time_study"):
        manifest = SplitManifest.model_validate_json(
            (ROOT / f"{split}.manifest.v1.json").read_text(encoding="utf-8")
        )
        assert manifest.split == split
        if split == "time_study":
            assert manifest.state == "planned"
            assert not manifest.entries
        else:
            assert manifest.state == ("sealed" if split == "holdout" else "exposed")
            assert (
                len(manifest.entries) == {"development": 24, "regression": 3, "holdout": 40}[split]
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("holdout_families", 10),
        ("critical_failures_allowed", 1),
        ("timing_terminal_contract", "any_finished_attempt"),
        ("primary_repeats", 2),
    ],
)
def test_frozen_contract_rejects_weakened_gate(field: str, value: object) -> None:
    data = json.loads((ROOT / "measurement-contract.v1.json").read_text(encoding="utf-8"))
    data[field] = value
    with pytest.raises(ValidationError):
        MeasurementContract.model_validate(data)


@pytest.mark.parametrize(
    "instant", ["2025-12-31T23:59:59Z", "2026-02-01T00:00:00Z", "2026-01-15T00:00:00"]
)
def test_policy_rejects_expired_future_or_naive_applicability(instant: str) -> None:
    data = _policy()
    data["applicable_at"] = instant
    with pytest.raises(ValidationError):
        PolicyExpectation.model_validate(data)


def test_policy_start_boundary_is_inclusive() -> None:
    data = _policy()
    data["applicable_at"] = data["effective_from"]
    PolicyExpectation.model_validate(data)


def test_valid_oracle_is_schema_example_not_product_result() -> None:
    assert OracleLabel.model_validate(_label()).expected_terminal == "verified_resolution"


@pytest.mark.parametrize(
    "mutation",
    [
        {"automation_eligible": True},
        {"escalation_required": True},
        {"expected_terminal": "safe_escalation"},
        {"policy_expectation": "missing"},
        {"policies": []},
        {"forbidden_action_types": ["refund"]},
        {"derived_from_product_output": True},
        {"provenance": "independent_human_review"},
        {"adjudicated_at": "2026-10-13T00:00:00"},
    ],
)
def test_oracle_rejects_contradictory_or_unsubstantiated_contract(
    mutation: dict[str, Any],
) -> None:
    data = _label()
    data.update(mutation)
    with pytest.raises(ValidationError):
        OracleLabel.model_validate(data)


def test_safe_escalation_requires_receipts_without_counting_as_resolution() -> None:
    data = _label()
    data.update(
        expected_terminal="safe_escalation",
        expected_actions=[],
        reopen_days=[],
        escalation_required=True,
        escalation_queue="supervisor",
        acknowledgement_required=True,
    )
    assert not OracleLabel.model_validate(data).automation_eligible


@pytest.mark.parametrize(
    "field",
    [
        "config_sha256",
        "model_version",
        "product_revision",
        "prompt_version",
        "scorer_version",
        "sealed_at",
    ],
)
def test_sealing_requires_reproducibility_identity(field: str) -> None:
    data = _manifest()
    data[field] = None
    with pytest.raises(ValidationError):
        SplitManifest.model_validate(data)


@pytest.mark.parametrize("split,count", [("holdout", 39), ("time_study", 11)])
def test_seal_rejects_small_family_population(split: str, count: int) -> None:
    with pytest.raises(ValidationError):
        SplitManifest.model_validate(_manifest(split, count))


def test_repeated_cases_do_not_increase_family_count() -> None:
    data = _manifest("holdout", 40)
    for entry in data["entries"]:
        entry["family_id"] = "one-family"
    with pytest.raises(ValidationError):
        SplitManifest.model_validate(data)


@pytest.mark.parametrize("field", ["family_id", "sop_family_id", "case_id", "input_sha256"])
def test_family_or_content_leakage_is_rejected(field: str) -> None:
    left = _manifest()
    right = _manifest("regression")
    right["entries"][0]["input_sha256"] = "d" * 64
    right["entries"][0][field] = left["entries"][0][field]
    with pytest.raises(ValueError, match="Split leakage"):
        validate_split_isolation(
            (SplitManifest.model_validate(left), SplitManifest.model_validate(right))
        )


def test_distinct_splits_pass_and_exposed_holdout_is_rejected() -> None:
    left = _manifest()
    right = _manifest("regression")
    right["entries"][0]["input_sha256"] = "d" * 64
    validate_split_isolation(
        (SplitManifest.model_validate(left), SplitManifest.model_validate(right))
    )
    exposed = _manifest("holdout", 40)
    exposed["state"] = "exposed"
    with pytest.raises(ValidationError):
        SplitManifest.model_validate(exposed)


def test_zero_denominator_is_unavailable_not_perfect() -> None:
    assert RateObservation(numerator=0, denominator=0).value is None
    assert RateObservation(numerator=38, denominator=40).value == 0.95
    with pytest.raises(ValidationError):
        RateObservation(numerator=1, denominator=0)


@pytest.mark.parametrize("numerator,denominator", [(-1, 1), (2, 1), (1, -1), (True, 1)])
def test_invalid_counts_are_rejected(numerator: int, denominator: int) -> None:
    with pytest.raises(ValidationError):
        RateObservation(numerator=numerator, denominator=denominator)


def test_same_outcome_timing_excludes_failed_manual_and_mismatched_terminal() -> None:
    data = dict(
        case_id="TIME-DEV",
        oracle_terminal="verified_resolution",
        manual_terminal="verified_resolution",
        assisted_terminal="verified_resolution",
        manual_correct=True,
        assisted_correct=True,
        manual_active_seconds=100,
        assisted_active_seconds=50,
    )
    assert PairedOutcome.model_validate(data).eligible_for_speedup
    for mutation in (
        {"manual_correct": False},
        {"manual_terminal": "open"},
        {"manual_terminal": "safe_escalation"},
        {"assisted_correct": False},
    ):
        changed = deepcopy(data)
        changed.update(mutation)
        assert not PairedOutcome.model_validate(changed).eligible_for_speedup
