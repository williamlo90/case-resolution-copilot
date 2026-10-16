from typing import Any

import pytest

from app.domain.controlled_operations import OPERATIONS, operation_draft
from app.domain.resolution import VerificationState
from app.integrations.action_gateway import (
    ActionGatewayError,
    ActionGatewayRequest,
    DeterministicActionGateway,
    GatewayBehavior,
)
from tests.unit.test_controlled_operations import operation_workspace


def gateway_request(action_type: str) -> ActionGatewayRequest:
    workspace, _ = operation_workspace(action_type)
    action = operation_draft(workspace, action_type)
    return ActionGatewayRequest(
        action_id="CONTROLLED-1",
        action_type=action.type,
        target=action.parameters["external_reference"],
        parameters=action.parameters,
        impact_amount=action.impact_amount,
        impact_currency=action.impact_currency,
        idempotency_key="controlled-operation-00001",
    )


@pytest.mark.parametrize("action_type", list(OPERATIONS))
def test_controlled_target_applies_a_real_synthetic_change_once(action_type: str) -> None:
    request = gateway_request(action_type)
    initial = {
        "owner": "SYNTHETIC-OWNER-1",
        "invoice_state": "draft",
        "currency": "USD",
        "active_sessions": "3",
        "credited_minor": "0",
    }
    gateway = DeterministicActionGateway(objects={request.target: initial})
    args: dict[str, Any] = dict(
        adapter_key="deterministic_demo",
        provider_type=OPERATIONS[action_type].provider,
        request=request,
    )
    receipt = gateway.execute(**args)
    assert gateway.execute(**args).duplicate
    assert len(gateway.controlled_target.effects) == 1
    assert gateway.controlled_target.objects[request.target] != initial
    lookup = gateway.reconcile(**args, external_reference=receipt.external_reference)
    assert lookup.readback is not None and lookup.readback.status is VerificationState.VERIFIED
    assert lookup.readback.observed_parameters == request.parameters
    assert lookup.readback.effect_count == 1


def test_timeout_after_rename_reads_business_state_and_detects_later_change() -> None:
    request = gateway_request("rename_account")
    gateway = DeterministicActionGateway(
        objects={request.target: {"owner": "SYNTHETIC-OWNER-1", "new_name": "old"}},
        behaviors={"rename_account": GatewayBehavior.OUTCOME_UNKNOWN_ACCEPTED},
    )
    args: dict[str, Any] = dict(
        adapter_key="deterministic_demo", provider_type="identity", request=request
    )
    with pytest.raises(ActionGatewayError, match="accepted"):
        gateway.execute(**args)
    assert gateway.controlled_target.objects[request.target]["new_name"] == "synthetic-new-value"
    lookup = gateway.reconcile(**args, external_reference=None)
    assert lookup.readback is not None and lookup.readback.status is VerificationState.VERIFIED
    gateway.controlled_target.objects[request.target]["new_name"] = "changed-again"
    lookup = gateway.reconcile(**args, external_reference=None)
    assert lookup.readback is not None and lookup.readback.status is VerificationState.MISMATCH
    assert lookup.readback.observed_parameters["new_name"] == "changed-again"
    with pytest.raises(ActionGatewayError, match="different payload"):
        gateway.execute(**{**args, "request": request.model_copy(update={"target": "another"})})
    assert len(gateway.controlled_target.effects) == 1


@pytest.mark.parametrize("fault", ["absent_target", "wrong_owner", "extra_field", "wrong_scope"])
def test_invalid_controlled_effect_never_reaches_target(fault: str) -> None:
    request = gateway_request("rename_account")
    objects = {request.target: {"owner": "SYNTHETIC-OWNER-1"}}
    if fault == "absent_target":
        objects = {}
    elif fault == "wrong_owner":
        objects[request.target]["owner"] = "OTHER-OWNER"
    elif fault == "extra_field":
        request.parameters["disable_security"] = "true"
    else:
        request.parameters["access_scope"] = "all_sessions"
    gateway = DeterministicActionGateway(objects=objects)
    with pytest.raises(ActionGatewayError):
        gateway.execute(adapter_key="deterministic_demo", provider_type="identity", request=request)
    assert gateway.controlled_target.objects == objects
    assert not gateway.controlled_target.effects
