from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.resolution import ActionReadback, VerificationState, verify_readback

NOW = datetime(2026, 10, 13, tzinfo=UTC)


def proof() -> ActionReadback:
    return ActionReadback(
        operation_id="operation-00000001",
        external_reference="REF-1",
        action_type="refund",
        target="CHARGE-1",
        observed_parameters={"recipient": "original"},
        impact_amount=Decimal("100.00"),
        impact_currency="USD",
        status=VerificationState.VERIFIED,
        observed_at=NOW,
        effect_count=1,
    )


def check(value: ActionReadback | None) -> VerificationState:
    return verify_readback(
        proof=value,
        operation_id="operation-00000001",
        external_reference="REF-1",
        action_type="refund",
        target="CHARGE-1",
        parameters={"recipient": "original"},
        impact_amount=Decimal("100.00"),
        impact_currency="USD",
        now=NOW,
    )


def test_absent_readback_is_not_success() -> None:
    assert check(None) is VerificationState.UNKNOWN
    assert check(proof()) is VerificationState.VERIFIED


@pytest.mark.parametrize(
    "mutation",
    [
        {"operation_id": "operation-other001"},
        {"external_reference": "REF-2"},
        {"target": "CHARGE-2"},
        {"action_type": "account_recovery"},
        {"observed_parameters": {"recipient": "attacker"}},
        {"impact_amount": Decimal("101")},
        {"impact_currency": "IDR"},
        {"effect_count": 2},
        {"effect_count": 0},
    ],
)
def test_wrong_consequential_result_never_verifies(mutation: dict[str, object]) -> None:
    assert check(proof().model_copy(update=mutation)) is VerificationState.MISMATCH


@pytest.mark.parametrize(
    "status", [VerificationState.PENDING, VerificationState.FAILED, VerificationState.UNKNOWN]
)
def test_nonterminal_and_failed_results_are_not_success(status: VerificationState) -> None:
    assert check(proof().model_copy(update={"status": status})) is status


@pytest.mark.parametrize("offset", [-301, 1])
def test_stale_or_future_readback_requires_another_check(offset: int) -> None:
    assert (
        check(proof().model_copy(update={"observed_at": NOW + timedelta(seconds=offset)}))
        is VerificationState.UNKNOWN
    )


def test_readback_requires_aware_timestamp() -> None:
    data = proof().model_dump()
    data["observed_at"] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError):
        ActionReadback.model_validate(data)


def test_consequential_amount_is_part_of_payload_hash() -> None:
    from app.domain.resolution import payload_digest

    assert payload_digest("refund", "payment-1", {}, Decimal("10"), "USD") != payload_digest(
        "refund", "payment-1", {}, Decimal("100"), "USD"
    )
