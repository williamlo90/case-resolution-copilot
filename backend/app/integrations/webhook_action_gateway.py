import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Self

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.domain.actions import ActionSideEffectState
from app.domain.connections import ConnectionHealth
from app.integrations.action_gateway import (
    ActionGateway,
    ActionGatewayError,
    ActionGatewayReceipt,
    ActionGatewayRequest,
    ActionLookupResult,
)
from app.integrations.webhook_security import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    sign_webhook,
)

MAX_WEBHOOK_RESPONSE_BYTES = 256 * 1024


class _WebhookResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionWebhookReceipt(_WebhookResponse):
    external_reference: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=16, max_length=128)
    status: str = Field(min_length=1, max_length=64)
    data: dict[str, str] = Field(default_factory=dict, max_length=50)
    duplicate: bool = False

    @field_validator("data")
    @classmethod
    def validate_data(cls, value: dict[str, str]) -> dict[str, str]:
        if any(
            not key or len(key) > 100 or len(item) > 2000
            for key, item in value.items()
        ):
            raise ValueError("receipt data exceeds the supported size")
        return value


class ActionWebhookLookup(_WebhookResponse):
    found: bool | None
    receipt: ActionWebhookReceipt | None = None
    detail: str = Field(min_length=1, max_length=1000)
    absence_is_terminal: bool = False

    @model_validator(mode="after")
    def require_receipt_for_found_action(self) -> Self:
        if self.found is True and self.receipt is None:
            raise ValueError("a found action requires a receipt")
        if self.found is not True and self.receipt is not None:
            raise ValueError("an unconfirmed action cannot include a receipt")
        if self.absence_is_terminal and self.found is not False:
            raise ValueError("terminal absence evidence requires found=false")
        return self


class ActionWebhookHealth(_WebhookResponse):
    status: Literal["healthy", "degraded", "unavailable"]
    detail: str = Field(min_length=1, max_length=1000)


class SignedWebhookActionGateway(ActionGateway):
    def __init__(
        self,
        *,
        url: str,
        secret: str,
        timeout_seconds: float,
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._url = url
        self._secret = secret
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None
        self._clock = clock or (lambda: datetime.now(UTC))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def execute(
        self,
        *,
        adapter_key: str,
        provider_type: str,
        request: ActionGatewayRequest,
    ) -> ActionGatewayReceipt:
        self._require_adapter(adapter_key)
        response = self._dispatch(
            {
                "operation": "execute",
                "provider_type": provider_type,
                "action": request.model_dump(mode="json"),
            },
            side_effecting=True,
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise self._execution_http_error()
        try:
            payload = ActionWebhookReceipt.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise ActionGatewayError(
                "The target may have changed data but returned an invalid confirmation.",
                code="target_confirmation_invalid",
                side_effect_state=ActionSideEffectState.POSSIBLE,
                retryable=False,
            ) from exc
        receipt = self._receipt(payload, provider_type=provider_type)
        if receipt.idempotency_key != request.idempotency_key:
            raise ActionGatewayError(
                "The target confirmation did not match this action.",
                code="target_confirmation_mismatch",
                side_effect_state=ActionSideEffectState.POSSIBLE,
                retryable=False,
            )
        return receipt

    def reconcile(
        self,
        *,
        adapter_key: str,
        provider_type: str,
        request: ActionGatewayRequest,
        external_reference: str | None,
    ) -> ActionLookupResult:
        self._require_adapter(adapter_key)
        try:
            response = self._dispatch(
                {
                    "operation": "reconcile",
                    "provider_type": provider_type,
                    "action": request.model_dump(mode="json"),
                    "external_reference": external_reference,
                },
                side_effecting=False,
            )
        except ActionGatewayError:
            return ActionLookupResult(
                found=None,
                receipt=None,
                detail="The target could not be checked. The outcome remains unknown.",
            )
        if response.status_code < 200 or response.status_code >= 300:
            return ActionLookupResult(
                found=None,
                receipt=None,
                detail="The target could not confirm the action outcome.",
            )
        try:
            payload = ActionWebhookLookup.model_validate(response.json())
            receipt = (
                self._receipt(payload.receipt, provider_type=provider_type)
                if payload.receipt is not None
                else None
            )
            if receipt is not None and receipt.idempotency_key != request.idempotency_key:
                raise ValueError("receipt idempotency key mismatch")
        except (ValueError, ValidationError):
            return ActionLookupResult(
                found=None,
                receipt=None,
                detail="The target returned an invalid reconciliation result.",
            )
        return ActionLookupResult(
            found=payload.found,
            receipt=receipt,
            detail=payload.detail,
            absence_is_terminal=payload.absence_is_terminal,
        )

    def check_health(
        self,
        *,
        adapter_key: str,
        provider_type: str,
    ) -> tuple[ConnectionHealth, str]:
        if adapter_key != "signed_webhook":
            return (
                ConnectionHealth.NOT_CONFIGURED,
                "No active adapter is configured for this connection.",
            )
        try:
            response = self._dispatch(
                {
                    "operation": "health",
                    "provider_type": provider_type,
                },
                side_effecting=False,
            )
            if response.status_code < 200 or response.status_code >= 300:
                raise ValueError("health request failed")
            payload = ActionWebhookHealth.model_validate(response.json())
        except (ActionGatewayError, ValueError, ValidationError):
            return (
                ConnectionHealth.UNAVAILABLE,
                "The action target did not complete its health check.",
            )
        return ConnectionHealth(payload.status), payload.detail

    def _dispatch(
        self,
        payload: dict[str, object],
        *,
        side_effecting: bool,
    ) -> httpx.Response:
        body = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        timestamp = int(self._clock().timestamp())
        action_payload = payload.get("action")
        idempotency_key = (
            str(action_payload.get("idempotency_key", ""))
            if isinstance(action_payload, dict)
            else ""
        )
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            TIMESTAMP_HEADER: str(timestamp),
            SIGNATURE_HEADER: sign_webhook(
                secret=self._secret,
                timestamp=timestamp,
                body=body,
            ),
        }
        try:
            with self._client.stream(
                "POST",
                self._url,
                content=body,
                headers=headers,
            ) as response:
                response_body = bytearray()
                for chunk in response.iter_bytes():
                    response_body.extend(chunk)
                    if len(response_body) > MAX_WEBHOOK_RESPONSE_BYTES:
                        raise ActionGatewayError(
                            "The target returned a confirmation that was too large.",
                            code="target_response_too_large",
                            side_effect_state=(
                                ActionSideEffectState.POSSIBLE
                                if side_effecting
                                else ActionSideEffectState.NOT_ATTEMPTED
                            ),
                            retryable=False,
                        )
                return httpx.Response(
                    status_code=response.status_code,
                    headers={
                        "content-type": response.headers.get(
                            "content-type",
                            "application/octet-stream",
                        )
                    },
                    content=bytes(response_body),
                )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            raise ActionGatewayError(
                "The target could not be reached before the action was sent.",
                code="target_unreachable",
                side_effect_state=ActionSideEffectState.NOT_ATTEMPTED,
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ActionGatewayError(
                (
                    "The target outcome could not be confirmed."
                    if side_effecting
                    else "The target could not be checked."
                ),
                code="target_request_interrupted",
                side_effect_state=(
                    ActionSideEffectState.POSSIBLE
                    if side_effecting
                    else ActionSideEffectState.NOT_ATTEMPTED
                ),
                retryable=not side_effecting,
            ) from exc

    @staticmethod
    def _execution_http_error() -> ActionGatewayError:
        return ActionGatewayError(
            "The target did not confirm whether the change was made.",
            code="target_outcome_unknown",
            side_effect_state=ActionSideEffectState.POSSIBLE,
            retryable=False,
        )

    @staticmethod
    def _receipt(
        payload: ActionWebhookReceipt,
        *,
        provider_type: str,
    ) -> ActionGatewayReceipt:
        return ActionGatewayReceipt(
            provider=provider_type,
            external_reference=payload.external_reference,
            idempotency_key=payload.idempotency_key,
            status=payload.status,
            data=payload.data,
            duplicate=payload.duplicate,
        )

    @staticmethod
    def _require_adapter(adapter_key: str) -> None:
        if adapter_key != "signed_webhook":
            raise ActionGatewayError(
                "No active adapter is configured for this connection.",
                code="connection_not_configured",
                side_effect_state=ActionSideEffectState.NOT_ATTEMPTED,
                retryable=False,
            )
