import pytest

from app.domain.actions import ActionSideEffectState
from app.domain.connections import ConnectionHealth
from app.integrations.action_gateway import (
    ActionGatewayError,
    ActionGatewayRequest,
    DeterministicActionGateway,
    GatewayBehavior,
)


def _request(
    *,
    action_type: str = "issue_refund",
    key: str = "a" * 64,
) -> ActionGatewayRequest:
    return ActionGatewayRequest(
        action_id="AC-TEST",
        action_type=action_type,
        target="ORDER-1001",
        parameters={"external_reference": "ORDER-1001"},
        idempotency_key=key,
    )


def test_success_is_idempotent_and_returns_the_same_receipt() -> None:
    gateway = DeterministicActionGateway()
    request = _request()

    first = gateway.execute(
        adapter_key="deterministic_demo",
        provider_type="billing",
        request=request,
    )
    second = gateway.execute(
        adapter_key="deterministic_demo",
        provider_type="billing",
        request=request,
    )

    assert first.external_reference == second.external_reference
    assert not first.duplicate
    assert second.duplicate


def test_safe_failure_proves_that_no_target_change_occurred() -> None:
    gateway = DeterministicActionGateway(behaviors={"issue_refund": GatewayBehavior.SAFE_FAILURE})

    with pytest.raises(ActionGatewayError) as captured:
        gateway.execute(
            adapter_key="deterministic_demo",
            provider_type="billing",
            request=_request(),
        )

    assert captured.value.side_effect_state is ActionSideEffectState.NONE
    assert captured.value.code == "target_rejected_before_change"


def test_unknown_accepted_outcome_is_resolved_by_read_only_reconciliation() -> None:
    gateway = DeterministicActionGateway(
        behaviors={
            "issue_refund": GatewayBehavior.OUTCOME_UNKNOWN_ACCEPTED,
        }
    )
    request = _request()

    with pytest.raises(ActionGatewayError) as captured:
        gateway.execute(
            adapter_key="deterministic_demo",
            provider_type="billing",
            request=request,
        )

    assert captured.value.side_effect_state is ActionSideEffectState.POSSIBLE
    result = gateway.reconcile(
        adapter_key="deterministic_demo",
        provider_type="billing",
        request=request,
        external_reference=None,
    )
    assert result.found is True
    assert result.receipt is not None
    assert result.receipt.idempotency_key == request.idempotency_key


def test_unknown_absent_outcome_becomes_safe_only_after_reconciliation() -> None:
    gateway = DeterministicActionGateway(
        behaviors={
            "issue_refund": GatewayBehavior.OUTCOME_UNKNOWN_ABSENT,
        }
    )
    request = _request()

    with pytest.raises(ActionGatewayError):
        gateway.execute(
            adapter_key="deterministic_demo",
            provider_type="billing",
            request=request,
        )
    result = gateway.reconcile(
        adapter_key="deterministic_demo",
        provider_type="billing",
        request=request,
        external_reference=None,
    )

    assert result.found is False
    assert result.receipt is None


def test_unconfigured_adapter_never_attempts_a_write() -> None:
    gateway = DeterministicActionGateway()

    with pytest.raises(ActionGatewayError) as captured:
        gateway.execute(
            adapter_key="unconfigured",
            provider_type="billing",
            request=_request(),
        )

    assert captured.value.side_effect_state is ActionSideEffectState.NOT_ATTEMPTED
    health, _ = gateway.check_health(
        adapter_key="unconfigured",
        provider_type="billing",
    )
    assert health is ConnectionHealth.NOT_CONFIGURED
