from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.actions import ActionSideEffectState
from app.domain.connections import ConnectionHealth


class GatewayBehavior(StrEnum):
    SUCCESS = "success"
    SAFE_FAILURE = "safe_failure"
    OUTCOME_UNKNOWN_ACCEPTED = "outcome_unknown_accepted"
    OUTCOME_UNKNOWN_ABSENT = "outcome_unknown_absent"
    RECONCILIATION_UNAVAILABLE = "reconciliation_unavailable"


class ActionGatewayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1, max_length=64)
    action_type: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=200)
    parameters: dict[str, str]
    idempotency_key: str = Field(min_length=16, max_length=128)


class ActionGatewayReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=100)
    external_reference: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=16, max_length=128)
    status: str = Field(min_length=1, max_length=64)
    data: dict[str, str]
    duplicate: bool = False


class ActionLookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool | None
    receipt: ActionGatewayReceipt | None
    detail: str = Field(min_length=1, max_length=1000)
    absence_is_terminal: bool = False

    @model_validator(mode="after")
    def validate_lookup_evidence(self) -> "ActionLookupResult":
        if self.found is True and self.receipt is None:
            raise ValueError("a confirmed action requires a receipt")
        if self.found is not True and self.receipt is not None:
            raise ValueError("an unconfirmed action cannot include a receipt")
        if self.absence_is_terminal and self.found is not False:
            raise ValueError("terminal absence evidence requires found=false")
        return self


class ActionGatewayError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        side_effect_state: ActionSideEffectState,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.side_effect_state = side_effect_state
        self.retryable = retryable


class ActionGateway:
    def execute(
        self,
        *,
        adapter_key: str,
        provider_type: str,
        request: ActionGatewayRequest,
    ) -> ActionGatewayReceipt:
        raise NotImplementedError

    def reconcile(
        self,
        *,
        adapter_key: str,
        provider_type: str,
        request: ActionGatewayRequest,
        external_reference: str | None,
    ) -> ActionLookupResult:
        raise NotImplementedError

    def check_health(
        self,
        *,
        adapter_key: str,
        provider_type: str,
    ) -> tuple[ConnectionHealth, str]:
        raise NotImplementedError


class RoutingActionGateway(ActionGateway):
    def __init__(self, gateways: dict[str, ActionGateway]) -> None:
        self._gateways = dict(gateways)

    def execute(
        self,
        *,
        adapter_key: str,
        provider_type: str,
        request: ActionGatewayRequest,
    ) -> ActionGatewayReceipt:
        return self._required_gateway(adapter_key).execute(
            adapter_key=adapter_key,
            provider_type=provider_type,
            request=request,
        )

    def reconcile(
        self,
        *,
        adapter_key: str,
        provider_type: str,
        request: ActionGatewayRequest,
        external_reference: str | None,
    ) -> ActionLookupResult:
        gateway = self._gateways.get(adapter_key)
        if gateway is None:
            return ActionLookupResult(
                found=None,
                receipt=None,
                detail="No active adapter is configured for this connection.",
            )
        return gateway.reconcile(
            adapter_key=adapter_key,
            provider_type=provider_type,
            request=request,
            external_reference=external_reference,
        )

    def check_health(
        self,
        *,
        adapter_key: str,
        provider_type: str,
    ) -> tuple[ConnectionHealth, str]:
        gateway = self._gateways.get(adapter_key)
        if gateway is None:
            return (
                ConnectionHealth.NOT_CONFIGURED,
                "No active adapter is configured for this connection.",
            )
        return gateway.check_health(
            adapter_key=adapter_key,
            provider_type=provider_type,
        )

    def _required_gateway(self, adapter_key: str) -> ActionGateway:
        gateway = self._gateways.get(adapter_key)
        if gateway is None:
            raise ActionGatewayError(
                "No active adapter is configured for this connection.",
                code="connection_not_configured",
                side_effect_state=ActionSideEffectState.NOT_ATTEMPTED,
                retryable=False,
            )
        return gateway


@dataclass
class _StoredOutcome:
    receipt: ActionGatewayReceipt


class DeterministicActionGateway(ActionGateway):
    """Credential-free, bounded action adapter used for demo and deterministic tests."""

    def __init__(
        self,
        *,
        behaviors: dict[str, GatewayBehavior] | None = None,
        health: dict[str, ConnectionHealth] | None = None,
    ) -> None:
        self._behaviors = behaviors or {}
        self._health = health or {}
        self._outcomes: dict[str, _StoredOutcome] = {}

    def execute(
        self,
        *,
        adapter_key: str,
        provider_type: str,
        request: ActionGatewayRequest,
    ) -> ActionGatewayReceipt:
        self._require_demo_adapter(adapter_key)
        existing = self._outcomes.get(request.idempotency_key)
        if existing is not None:
            return existing.receipt.model_copy(update={"duplicate": True})
        behavior = self._behaviors.get(
            request.action_type,
            GatewayBehavior.SUCCESS,
        )
        if behavior is GatewayBehavior.SAFE_FAILURE:
            raise ActionGatewayError(
                "The demo target rejected the request before any change.",
                code="target_rejected_before_change",
                side_effect_state=ActionSideEffectState.NONE,
                retryable=False,
            )
        receipt = self._receipt(provider_type, request)
        if behavior is GatewayBehavior.OUTCOME_UNKNOWN_ACCEPTED:
            self._outcomes[request.idempotency_key] = _StoredOutcome(receipt)
            raise ActionGatewayError(
                "The demo target accepted the request but did not return a receipt.",
                code="target_timeout_after_acceptance",
                side_effect_state=ActionSideEffectState.POSSIBLE,
                retryable=False,
            )
        if behavior in {
            GatewayBehavior.OUTCOME_UNKNOWN_ABSENT,
            GatewayBehavior.RECONCILIATION_UNAVAILABLE,
        }:
            raise ActionGatewayError(
                "The demo target stopped responding before the outcome was known.",
                code="target_outcome_unknown",
                side_effect_state=ActionSideEffectState.POSSIBLE,
                retryable=False,
            )
        self._outcomes[request.idempotency_key] = _StoredOutcome(receipt)
        return receipt

    def reconcile(
        self,
        *,
        adapter_key: str,
        provider_type: str,
        request: ActionGatewayRequest,
        external_reference: str | None,
    ) -> ActionLookupResult:
        del provider_type
        self._require_demo_adapter(adapter_key)
        behavior = self._behaviors.get(
            request.action_type,
            GatewayBehavior.SUCCESS,
        )
        if behavior is GatewayBehavior.RECONCILIATION_UNAVAILABLE:
            return ActionLookupResult(
                found=None,
                receipt=None,
                detail="The demo target is unavailable; the outcome is still unknown.",
            )
        stored = self._outcomes.get(request.idempotency_key)
        if stored is None:
            return ActionLookupResult(
                found=False,
                receipt=None,
                detail="No matching target change was found.",
                absence_is_terminal=(
                    behavior is GatewayBehavior.OUTCOME_UNKNOWN_ABSENT
                ),
            )
        if (
            external_reference is not None
            and stored.receipt.external_reference != external_reference
        ):
            return ActionLookupResult(
                found=None,
                receipt=None,
                detail="The recorded reference does not match the target result.",
            )
        return ActionLookupResult(
            found=True,
            receipt=stored.receipt.model_copy(deep=True),
            detail="The target confirmed the recorded change.",
        )

    def check_health(
        self,
        *,
        adapter_key: str,
        provider_type: str,
    ) -> tuple[ConnectionHealth, str]:
        if adapter_key != "deterministic_demo":
            return (
                ConnectionHealth.NOT_CONFIGURED,
                "No active adapter is configured for this connection.",
            )
        health = self._health.get(provider_type, ConnectionHealth.HEALTHY)
        detail = {
            ConnectionHealth.HEALTHY: "The deterministic demo connection is ready.",
            ConnectionHealth.DEGRADED: "The deterministic demo connection is responding slowly.",
            ConnectionHealth.UNAVAILABLE: "The deterministic demo connection is unavailable.",
            ConnectionHealth.NOT_CONFIGURED: "The deterministic demo connection is not configured.",
        }[health]
        return health, detail

    @staticmethod
    def _require_demo_adapter(adapter_key: str) -> None:
        if adapter_key != "deterministic_demo":
            raise ActionGatewayError(
                "No active adapter is configured for this connection.",
                code="connection_not_configured",
                side_effect_state=ActionSideEffectState.NOT_ATTEMPTED,
                retryable=False,
            )

    @staticmethod
    def _receipt(
        provider_type: str,
        request: ActionGatewayRequest,
    ) -> ActionGatewayReceipt:
        suffix = sha256(request.idempotency_key.encode()).hexdigest()[:16].upper()
        prefix = (
            "".join(character for character in provider_type.upper() if character.isalnum())[:6]
            or "ACTION"
        )
        return ActionGatewayReceipt(
            provider=provider_type,
            external_reference=f"{prefix}-{suffix}",
            idempotency_key=request.idempotency_key,
            status="accepted",
            data={
                "action_type": request.action_type,
                "target": request.target,
            },
        )
