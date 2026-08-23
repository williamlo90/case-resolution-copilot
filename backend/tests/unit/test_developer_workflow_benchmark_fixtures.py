import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest

from app.domain.cases import CaseCreate

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_ROOT = REPOSITORY_ROOT / "docs" / "evidence" / "developer-workflow-benchmark"
MANUAL_DIRECTORY = BENCHMARK_ROOT / "manual-workspace" / "cases"
PRODUCT_DIRECTORY = BENCHMARK_ROOT / "product-fixtures"
ANSWER_LEAK_KEYS = {
    "answer",
    "answer_key",
    "correct_disposition",
    "expected",
    "expected_answer",
    "expected_disposition",
    "forbidden_actions",
    "next_safe_action",
}


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixtures(directory: Path) -> list[dict[str, Any]]:
    return [_load(path) for path in sorted(directory.glob("*.json"))]


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _keys(child)}
    return set()


@pytest.fixture(scope="module")
def manual_fixtures() -> list[dict[str, Any]]:
    return _fixtures(MANUAL_DIRECTORY)


@pytest.fixture(scope="module")
def product_fixtures() -> list[dict[str, Any]]:
    return _fixtures(PRODUCT_DIRECTORY)


def test_fixture_inventory_and_domain_contract(
    manual_fixtures: list[dict[str, Any]], product_fixtures: list[dict[str, Any]]
) -> None:
    assert len(manual_fixtures) == 3
    assert len(product_fixtures) == 3
    assert {item["condition"] for item in manual_fixtures} == {"manual"}
    assert {item["condition"] for item in product_fixtures} == {"copilot"}

    for fixture in [*manual_fixtures, *product_fixtures]:
        command = CaseCreate.model_validate(fixture["case"])
        assert len(fixture["conversation"]) == 8
        assert len(command.business_contexts) == 4
        assert len(fixture["policy_ids"]) == 4
        assert fixture["conversation"][0]["body"] == command.request.customer_message
        assert fixture["conversation"][0]["channel"] == command.request.channel.value
        assert not (ANSWER_LEAK_KEYS & _keys(fixture))


def test_pair_manifest_and_structural_parity(
    manual_fixtures: list[dict[str, Any]], product_fixtures: list[dict[str, Any]]
) -> None:
    manifest = _load(BENCHMARK_ROOT / "pair-manifest.json")
    assert len(manifest["pairs"]) == 3
    manual_by_pair = {item["pair_id"]: item for item in manual_fixtures}
    product_by_pair = {item["pair_id"]: item for item in product_fixtures}
    assert (
        set(manual_by_pair)
        == set(product_by_pair)
        == {item["pair_id"] for item in manifest["pairs"]}
    )

    for pair in manifest["pairs"]:
        manual = manual_by_pair[pair["pair_id"]]
        product = product_by_pair[pair["pair_id"]]
        assert manual["fixture_id"] == pair["manual_fixture"]
        assert product["fixture_id"] == pair["product_fixture"]
        assert manual["case"]["category"] == product["case"]["category"] == pair["category"]
        assert (
            len(manual["conversation"])
            == len(product["conversation"])
            == pair["conversation_entries"]
        )
        assert (
            len(manual["case"]["business_contexts"])
            == len(product["case"]["business_contexts"])
            == pair["business_records"]
        )
        assert len(manual["policy_ids"]) == len(product["policy_ids"]) == pair["policy_entries"]
        assert Counter(item["type"] for item in manual["case"]["business_contexts"]) == Counter(
            item["type"] for item in product["case"]["business_contexts"]
        )


def test_frozen_manifest_matches_public_fixtures_and_local_answer_key() -> None:
    manifest = _load(BENCHMARK_ROOT / "frozen-manifest.json")
    assert manifest["schema_version"] == "developer-workflow-benchmark-freeze.v1"
    assert manifest["hash_algorithm"] == "sha256"

    public_files = cast(dict[str, str], manifest["public_files"])
    assert len(public_files) == 8
    for relative_path, expected_digest in public_files.items():
        assert _sha256(BENCHMARK_ROOT / relative_path) == expected_digest

    answer_key = cast(dict[str, str], manifest["withheld_answer_key"])
    assert answer_key["repository_policy"] == "ignored"
    assert len(answer_key["sha256_commitment"]) == 64
    answer_key_path = BENCHMARK_ROOT / answer_key["path"]
    if answer_key_path.exists():
        assert _sha256(answer_key_path) == answer_key["sha256_commitment"]


@pytest.mark.parametrize("directory", [MANUAL_DIRECTORY, PRODUCT_DIRECTORY])
def test_billing_pair_requires_second_settled_payment_reference(directory: Path) -> None:
    fixture = next(item for item in _fixtures(directory) if item["pair_id"] == "billing")
    payments = [item for item in fixture["case"]["business_contexts"] if item["type"] == "payment"]
    assert len(payments) == 1
    assert int(payments[0]["fields"]["attempt_count"]) >= 2
    assert len({item["source_reference"] for item in payments}) == 1


@pytest.mark.parametrize("directory", [MANUAL_DIRECTORY, PRODUCT_DIRECTORY])
def test_refund_pair_contains_eligible_order_and_delivery_state(directory: Path) -> None:
    fixture = next(item for item in _fixtures(directory) if item["pair_id"] == "refund")
    contexts = fixture["case"]["business_contexts"]
    assert any(item["type"] == "order" and item["status"] == "unused" for item in contexts)
    assert any(item["type"] == "delivery" and item["status"] == "not_started" for item in contexts)


@pytest.mark.parametrize("directory", [MANUAL_DIRECTORY, PRODUCT_DIRECTORY])
def test_account_pair_blocks_recovery_on_stale_unverified_context(directory: Path) -> None:
    fixture = next(item for item in _fixtures(directory) if item["pair_id"] == "account_recovery")
    assert fixture["case"]["source_freshness"] == "stale"
    accounts = [item for item in fixture["case"]["business_contexts"] if item["type"] == "account"]
    assert len(accounts) == 1
    assert accounts[0]["freshness"] == "stale"
    assert accounts[0]["fields"]["identity_check"] != "verified"


def test_safety_scenario_selectors_still_exist() -> None:
    scenarios = _load(BENCHMARK_ROOT / "safety-scenarios.json")["scenarios"]
    assert len(scenarios) == 3
    for scenario in scenarios:
        test_file = REPOSITORY_ROOT / "backend" / scenario["test_file"]
        assert test_file.is_file()
        assert f"def {scenario['test_selector']}(" in test_file.read_text(encoding="utf-8")
