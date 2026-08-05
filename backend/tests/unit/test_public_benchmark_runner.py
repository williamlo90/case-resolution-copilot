from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.evaluation.public_benchmark.baseline import DeterministicPublicBaseline
from app.evaluation.public_benchmark.models import (
    ArtifactManifest,
    CfpbInputPayload,
    CfpbInputRecord,
    CfpbLabelPayload,
    CfpbLabelRecord,
    FosInputPayload,
    FosInputRecord,
    FosLabelPayload,
    FosLabelRecord,
    PublicBenchmarkManifest,
    SourceSnapshot,
    UciInputPayload,
    UciInputRecord,
    UciLabelPayload,
    UciLabelRecord,
    UciTransaction,
    ValidationSummary,
)
from app.evaluation.public_benchmark.predictions import UciPredictionRecord
from app.evaluation.public_benchmark.runner import (
    generate_predictions,
    run_public_benchmark,
    score_predictions,
)
from app.evaluation.public_benchmark.storage import (
    atomic_write_json,
    relative_manifest_path,
    sha256_file,
    write_jsonl,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
HASH = "a" * 64


def test_deterministic_baseline_matches_explicit_uci_relationship() -> None:
    predictor = DeterministicPublicBaseline()
    matched_input, _ = _uci_records(matched=True, suffix="match")
    unrelated_input, _ = _uci_records(matched=False, suffix="unrelated")

    matched = predictor.predict(matched_input)
    unrelated = predictor.predict(unrelated_input)

    assert isinstance(matched, UciPredictionRecord)
    assert isinstance(unrelated, UciPredictionRecord)
    assert matched.payload.relationship == "candidate_cancellation_match"
    assert matched.payload.expected_original_invoice == "SALE-100"
    assert unrelated.payload.relationship == "unrelated_pair"
    assert unrelated.payload.expected_original_invoice is None


def test_blind_run_persists_predictions_before_label_aware_scoring(tmp_path: Path) -> None:
    _write_benchmark(tmp_path)

    manifest = generate_predictions(tmp_path, run_id="test-baseline-v1", clock=lambda: NOW)

    manifest_text = (tmp_path / "runs/test-baseline-v1/prediction-manifest.json").read_text()
    assert manifest.phase_contract == "inputs_only"
    assert "labels.jsonl" not in manifest_text
    assert manifest.predictions.records == 4
    assert not (tmp_path / "runs/test-baseline-v1/report.json").exists()

    report = score_predictions(tmp_path, run_id="test-baseline-v1", clock=lambda: NOW)

    assert [suite.suite for suite in report.suites] == ["cfpb", "fos", "uci"]
    assert next(suite for suite in report.suites if suite.suite == "uci").accuracy == 1.0
    assert len(report.integrity_checks) == 9
    assert (tmp_path / "runs/test-baseline-v1/report.md").is_file()


def test_scoring_fails_if_inputs_change_after_prediction(tmp_path: Path) -> None:
    _write_benchmark(tmp_path)
    generate_predictions(tmp_path, run_id="test-baseline-v1", clock=lambda: NOW)
    path = tmp_path / "prepared/cfpb/inputs.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="input artifacts changed"):
        score_predictions(tmp_path, run_id="test-baseline-v1", clock=lambda: NOW)


def test_scoring_fails_if_prediction_artifact_is_tampered(tmp_path: Path) -> None:
    _write_benchmark(tmp_path)
    generate_predictions(tmp_path, run_id="test-baseline-v1", clock=lambda: NOW)
    path = tmp_path / "runs/test-baseline-v1/predictions.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Prediction artifact byte count changed"):
        score_predictions(tmp_path, run_id="test-baseline-v1", clock=lambda: NOW)


def test_scoring_fails_if_labels_change_after_preparation(tmp_path: Path) -> None:
    _write_benchmark(tmp_path)
    generate_predictions(tmp_path, run_id="test-baseline-v1", clock=lambda: NOW)
    path = tmp_path / "prepared/fos/labels.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Manifest byte count changed"):
        score_predictions(tmp_path, run_id="test-baseline-v1", clock=lambda: NOW)


def test_report_keeps_different_tasks_separate(tmp_path: Path) -> None:
    _write_benchmark(tmp_path)

    report = run_public_benchmark(
        tmp_path,
        run_id="test-baseline-v1",
        clock=lambda: NOW,
    )
    serialized = report.model_dump(mode="json")

    assert "overall_accuracy" not in serialized
    assert {suite["suite"] for suite in serialized["suites"]} == {"cfpb", "fos", "uci"}
    markdown = (tmp_path / "runs/test-baseline-v1/report.md").read_text(encoding="utf-8")
    assert "There is no cross-suite aggregate" in markdown


def test_prediction_rejects_unsafe_run_id_before_writing(tmp_path: Path) -> None:
    _write_benchmark(tmp_path)

    with pytest.raises(ValueError):
        generate_predictions(tmp_path, run_id="../outside", clock=lambda: NOW)

    assert not (tmp_path.parent / "outside").exists()


def _write_benchmark(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    cfpb_input, cfpb_label = _cfpb_records()
    fos_input, fos_label = _fos_records()
    matched_input, matched_label = _uci_records(matched=True, suffix="match")
    unrelated_input, unrelated_label = _uci_records(
        matched=False,
        suffix="unrelated",
    )
    artifacts: list[ArtifactManifest] = []
    counts = {"cfpb": 0, "fos": 0, "uci": 0}
    for suite, inputs, labels in (
        ("cfpb", [cfpb_input], [cfpb_label]),
        ("fos", [fos_input], [fos_label]),
        ("uci", [matched_input, unrelated_input], [matched_label, unrelated_label]),
    ):
        input_path = root / "prepared" / suite / "inputs.jsonl"
        label_path = root / "prepared" / suite / "labels.jsonl"
        input_count = write_jsonl(root, input_path, inputs)
        label_count = write_jsonl(root, label_path, labels)
        counts[suite] = input_count
        artifacts.extend(
            (
                ArtifactManifest(
                    suite=suite,
                    kind="prepared_input",
                    path=relative_manifest_path(root, input_path),
                    sha256=sha256_file(input_path),
                    bytes=input_path.stat().st_size,
                    records=input_count,
                ),
                ArtifactManifest(
                    suite=suite,
                    kind="prepared_label",
                    path=relative_manifest_path(root, label_path),
                    sha256=sha256_file(label_path),
                    bytes=label_path.stat().st_size,
                    records=label_count,
                ),
            )
        )
    manifest = PublicBenchmarkManifest(
        generated_at=NOW,
        config_sha256=HASH,
        sources=[
            SourceSnapshot(
                suite=suite,
                name=f"{suite.upper()} fixture",
                canonical_url=f"https://example.test/{suite}",
                license="fixture",
                retrieved_at=NOW,
                details={"fixture": True},
            )
            for suite in ("cfpb", "fos", "uci")
        ],
        artifacts=artifacts,
        validation=ValidationSummary(
            passed=True,
            input_records=counts,
            label_records=counts,
            checks=["fixture_validated"],
        ),
    )
    atomic_write_json(root, root / "manifest.json", manifest.model_dump(mode="json"))


def _cfpb_records() -> tuple[CfpbInputRecord, CfpbLabelRecord]:
    common = {
        "record_id": "cfpb-fixture-1",
        "source_record_id": "fixture-cfpb-1",
        "source_url": "https://example.test/cfpb/1",
        "retrieved_at": NOW,
        "source_artifact_sha256": HASH,
    }
    return (
        CfpbInputRecord(
            **common,
            payload=CfpbInputPayload(
                received_on=NOW.date(),
                product="Checking account",
                issue="Incorrect fee",
                submitted_via="Web",
                narrative=(
                    "The customer requests a refund after the same account fee was charged twice."
                ),
            ),
        ),
        CfpbLabelRecord(
            **common,
            payload=CfpbLabelPayload(
                company_response="Closed with monetary relief",
                timely_response=True,
            ),
        ),
    )


def _fos_records() -> tuple[FosInputRecord, FosLabelRecord]:
    common = {
        "record_id": "fos-fixture-1",
        "source_record_id": "fixture-fos-1",
        "source_url": "https://example.test/fos/1",
        "retrieved_at": NOW,
        "source_artifact_sha256": HASH,
    }
    return (
        FosInputRecord(
            **common,
            payload=FosInputPayload(
                case_text=(
                    "The customer reported a scam after sending funds to a false investment. "
                    "The bank declined reimbursement. Account statements, correspondence, payment "
                    "records, and a detailed chronology were supplied by both parties. The "
                    "customer said the warnings did not describe the actual scam and documented "
                    "the loss."
                ),
                removed_outcome_fragments=2,
            ),
        ),
        FosLabelRecord(
            **common,
            payload=FosLabelPayload(
                outcome="upheld",
                final_decision_text="The complaint succeeded and reimbursement was directed.",
            ),
        ),
    )


def _uci_records(
    *,
    matched: bool,
    suffix: str,
) -> tuple[UciInputRecord, UciLabelRecord]:
    common = {
        "record_id": f"uci-fixture-{suffix}",
        "source_record_id": f"fixture-uci-{suffix}",
        "source_url": "https://example.test/uci",
        "retrieved_at": NOW,
        "source_artifact_sha256": HASH,
    }
    sale = UciTransaction(
        invoice_id="SALE-100",
        stock_code="SKU-1",
        description="Fixture item",
        quantity=2,
        invoice_at=NOW,
        unit_price="15.00",
        customer_ref="customer-aaaaaaaaaaaa",
        country="United Kingdom",
    )
    cancellation = UciTransaction(
        invoice_id="CANCEL-100",
        stock_code="SKU-1" if matched else "SKU-2",
        description="Fixture item",
        quantity=-2,
        invoice_at=NOW + timedelta(hours=1),
        unit_price="15.00",
        customer_ref="customer-aaaaaaaaaaaa",
        country="United Kingdom",
    )
    relationship = "candidate_cancellation_match" if matched else "unrelated_pair"
    return (
        UciInputRecord(
            **common,
            payload=UciInputPayload(
                sale_transaction=sale,
                cancellation_transaction=cancellation,
            ),
        ),
        UciLabelRecord(
            **common,
            payload=UciLabelPayload(
                relationship=relationship,
                label_basis=("derived_exact_match_rule" if matched else "constructed_negative"),
                expected_original_invoice="SALE-100" if matched else None,
            ),
        ),
    )
