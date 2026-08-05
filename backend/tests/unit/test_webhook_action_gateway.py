import json
from datetime import UTC, datetime

import httpx
import pytest

from app.domain.actions import ActionSideEffectState
from app.domain.connections import ConnectionHealth
from app.integrations.action_gateway import (
    ActionGatewayError,
    ActionGatewayRequest,
)
from app.integrations.webhook_action_gateway import (
    MAX_WEBHOOK_RESPONSE_BYTES,
    SignedWebhookActionGateway,
)
from app.integrations.webhook_security import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    verify_webhook,
)

SECRET = "action-signing-secret-with-at-least-32-characters"
NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def _request() -> ActionGatewayRequest:
    return ActionGatewayRequest(
        action_id="AC-TEST",
        action_type="issue_refund",
        target="ORDER-1001",
        parameters={"amount": "125.00", "currency": "USD"},
        idempotency_key="a" * 64,
    )


def _gateway(
    handler: httpx.MockTransport,
) -> SignedWebhookActionGateway:
    return SignedWebhookActionGateway(
        url="https://actions.example.com/support",
        secret=SECRET,
        timeout_seconds=5,
        client=httpx.Client(transport=handler),
        clock=lambda: NOW,
    )


def test_signed_action_execution_returns_an_attributable_receipt() -> None:
    request = _request()

    def respond(http_request: httpx.Request) -> httpx.Response:
        verify_webhook(
            secret=SECRET,
            timestamp_header=http_request.headers[TIMESTAMP_HEADER],
            signature_header=http_request.headers[SIGNATURE_HEADER],
            body=http_request.content,
            max_age_seconds=300,
            now=NOW,
        )
        payload = json.loads(http_request.content)
        assert payload["operation"] == "execute"
        assert http_request.headers["Idempotency-Key"] == request.idempotency_key
        return httpx.Response(
            200,
            json={
                "external_reference": "TARGET-1001",
                "idempotency_key": request.idempotency_key,
                "status": "completed",
                "data": {"result": "refunded"},
                "duplicate": False,
            },
        )

    receipt = _gateway(httpx.MockTransport(respond)).execute(
        adapter_key="signed_webhook",
        provider_type="business_operations",
        request=request,
    )

    assert receipt.external_reference == "TARGET-1001"
    assert receipt.provider == "business_operations"


@pytest.mark.parametrize(
    ("status_code", "expected_state"),
    [
        (401, ActionSideEffectState.POSSIBLE),
        (422, ActionSideEffectState.POSSIBLE),
        (429, ActionSideEffectState.POSSIBLE),
        (500, ActionSideEffectState.POSSIBLE),
    ],
)
def test_signed_action_execution_maps_failure_side_effect_state(
    status_code: int,
    expected_state: ActionSideEffectState,
) -> None:
    gateway = _gateway(
        httpx.MockTransport(lambda _: httpx.Response(status_code, json={"error": "failed"}))
    )

    with pytest.raises(ActionGatewayError) as captured:
        gateway.execute(
            adapter_key="signed_webhook",
            provider_type="business_operations",
            request=_request(),
        )

    assert captured.value.side_effect_state is expected_state
    assert captured.value.code == "target_outcome_unknown"
    assert captured.value.retryable is False


def test_signed_action_reconciliation_never_issues_another_execute_operation() -> None:
    request = _request()

    def respond(http_request: httpx.Request) -> httpx.Response:
        payload = json.loads(http_request.content)
        if payload["operation"] == "health":
            return httpx.Response(
                200,
                json={"status": "healthy", "detail": "Sandbox target is ready."},
            )
        assert payload["operation"] == "reconcile"
        return httpx.Response(
            200,
            json={
                "found": True,
                "receipt": {
                    "external_reference": "TARGET-1001",
                    "idempotency_key": request.idempotency_key,
                    "status": "completed",
                    "data": {},
                    "duplicate": False,
                },
                "detail": "The target confirmed the action.",
            },
        )

    gateway = _gateway(httpx.MockTransport(respond))
    result = gateway.reconcile(
        adapter_key="signed_webhook",
        provider_type="business_operations",
        request=request,
        external_reference=None,
    )
    health, detail = gateway.check_health(
        adapter_key="signed_webhook",
        provider_type="business_operations",
    )

    assert result.found is True
    assert result.receipt is not None
    assert health is ConnectionHealth.HEALTHY
    assert detail == "Sandbox target is ready."


def test_invalid_success_response_is_treated_as_an_unknown_outcome() -> None:
    gateway = _gateway(
        httpx.MockTransport(
            lambda _: httpx.Response(200, json={"status": "completed"})
        )
    )

    with pytest.raises(ActionGatewayError) as captured:
        gateway.execute(
            adapter_key="signed_webhook",
            provider_type="business_operations",
            request=_request(),
        )

    assert captured.value.code == "target_confirmation_invalid"
    assert captured.value.side_effect_state is ActionSideEffectState.POSSIBLE


def test_oversized_execution_response_is_treated_as_an_unknown_outcome() -> None:
    gateway = _gateway(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=b"x" * (MAX_WEBHOOK_RESPONSE_BYTES + 1),
            )
        )
    )

    with pytest.raises(ActionGatewayError) as captured:
        gateway.execute(
            adapter_key="signed_webhook",
            provider_type="business_operations",
            request=_request(),
        )

    assert captured.value.code == "target_response_too_large"
    assert captured.value.side_effect_state is ActionSideEffectState.POSSIBLE


def test_reconciliation_rejects_a_receipt_without_a_confirmed_match() -> None:
    request = _request()
    gateway = _gateway(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "found": None,
                    "receipt": {
                        "external_reference": "TARGET-1001",
                        "idempotency_key": request.idempotency_key,
                        "status": "completed",
                        "data": {},
                        "duplicate": False,
                    },
                    "detail": "Target returned an inconsistent result.",
                },
            )
        )
    )

    result = gateway.reconcile(
        adapter_key="signed_webhook",
        provider_type="business_operations",
        request=request,
        external_reference=None,
    )

    assert result.found is None
    assert result.receipt is None
    assert result.detail == "The target returned an invalid reconciliation result."


@pytest.mark.parametrize(
    ("error_type", "expected_state"),
    [
        (httpx.ConnectTimeout, ActionSideEffectState.NOT_ATTEMPTED),
        (httpx.ReadTimeout, ActionSideEffectState.POSSIBLE),
    ],
)
def test_network_failures_preserve_side_effect_knowledge(
    error_type: type[httpx.RequestError],
    expected_state: ActionSideEffectState,
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise error_type("simulated timeout", request=request)

    with pytest.raises(ActionGatewayError) as captured:
        _gateway(httpx.MockTransport(fail)).execute(
            adapter_key="signed_webhook",
            provider_type="business_operations",
            request=_request(),
        )

    assert captured.value.side_effect_state is expected_state
