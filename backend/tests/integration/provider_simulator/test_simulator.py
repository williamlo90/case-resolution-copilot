from decimal import Decimal

import pytest

from app.integrations.provider_simulator import DeterministicProviderSimulator
from app.tools.contracts import (
    CreateCreditInput,
    LookupCreditInput,
    ProviderScenario,
    SideEffectState,
)
from app.tools.errors import ProviderPreSendTimeout, ProviderRejected, ProviderTimeout


def credit_input(
    scenario: ProviderScenario, *, idempotency_key: str = "credit-CASE-1042-v1"
) -> CreateCreditInput:
    return CreateCreditInput(
        account_id="ACCT-218",
        amount=Decimal("284.00"),
        currency="USD",
        reason_code="DUPLICATE_CHARGE",
        idempotency_key=idempotency_key,
        scenario=scenario,
    )


def lookup(key: str = "credit-CASE-1042-v1") -> LookupCreditInput:
    return LookupCreditInput(account_id="ACCT-218", idempotency_key=key)


def test_success_and_duplicate_key_return_same_logical_receipt() -> None:
    provider = DeterministicProviderSimulator()
    first = provider.create_credit_request(credit_input(ProviderScenario.SUCCESS))
    duplicate = provider.create_credit_request(
        credit_input(ProviderScenario.REJECT_BEFORE_SIDE_EFFECT)
    )
    assert duplicate.external_reference == first.external_reference
    assert duplicate.duplicate is True


def test_rejection_and_pre_send_timeout_have_no_side_effect() -> None:
    provider = DeterministicProviderSimulator()
    with pytest.raises(ProviderRejected) as rejected:
        provider.create_credit_request(credit_input(ProviderScenario.REJECT_BEFORE_SIDE_EFFECT))
    assert rejected.value.side_effect_state is SideEffectState.NONE
    assert provider.lookup_credit(lookup()).found is False

    with pytest.raises(ProviderPreSendTimeout) as timed_out:
        provider.create_credit_request(
            credit_input(ProviderScenario.TIMEOUT_BEFORE_SEND, idempotency_key="credit-pre-send")
        )
    assert timed_out.value.side_effect_state is SideEffectState.NOT_ATTEMPTED


def test_timeout_after_acceptance_is_reconciled_by_lookup() -> None:
    provider = DeterministicProviderSimulator()
    with pytest.raises(ProviderTimeout) as captured:
        provider.create_credit_request(credit_input(ProviderScenario.TIMEOUT_AFTER_ACCEPTANCE))
    assert captured.value.side_effect_state is SideEffectState.POSSIBLE
    assert provider.lookup_credit(lookup()).found is True


def test_delayed_postcondition_becomes_visible_deterministically() -> None:
    provider = DeterministicProviderSimulator()
    receipt = provider.create_credit_request(
        credit_input(ProviderScenario.DELAYED_POSTCONDITION, idempotency_key="credit-delayed")
    )
    request = LookupCreditInput(
        account_id="ACCT-218", external_reference=receipt.external_reference
    )
    assert provider.lookup_credit(request).found is False
    assert provider.lookup_credit(request).found is False
    assert provider.lookup_credit(request).found is True
