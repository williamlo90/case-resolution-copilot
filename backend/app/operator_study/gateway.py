"""Durable synthetic target; receipts and independent read-back survive cold starts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.actions import ActionSideEffectState
from app.domain.connections import ConnectionHealth
from app.domain.resolution import ActionReadback, VerificationState
from app.integrations.action_gateway import (
    ActionGateway,
    ActionGatewayError,
    ActionGatewayReceipt,
    ActionGatewayRequest,
    ActionLookupResult,
)
from app.integrations.controlled_target import ControlledTarget
from app.persistence.database import Database

from .storage import insert, record


class PersistentStudyGateway(ActionGateway):
    def __init__(self, database: Database) -> None:
        self.database = database

    def execute(
        self, *, adapter_key: str, provider_type: str, request: ActionGatewayRequest
    ) -> ActionGatewayReceipt:
        try:
            return self._execute(
                adapter_key=adapter_key, provider_type=provider_type, request=request
            )
        except ValueError as exc:
            raise ActionGatewayError(
                str(exc),
                code="study_target_rejected",
                side_effect_state=ActionSideEffectState.NONE,
                retryable=False,
            ) from exc

    def _execute(
        self, *, adapter_key: str, provider_type: str, request: ActionGatewayRequest
    ) -> ActionGatewayReceipt:
        if adapter_key != "deterministic_demo":
            raise ValueError("Study supports only the synthetic adapter")
        with self.database.session() as session:
            target = record(session, "target", request.target, lock=True)
            if target is None:
                raise ValueError("No study target is configured")
            existing = record(session, "effect", request.idempotency_key)
            payload = request.model_dump(mode="json")
            if existing is not None:
                if existing.value["request"] != payload:
                    raise ValueError("An operation ID cannot be reused for a different payload")
                return ActionGatewayReceipt.model_validate(existing.value["receipt"]).model_copy(
                    update={"duplicate": True}
                )
            independent = ControlledTarget({request.target: target.value})
            changes = independent.prepare(
                action_type=request.action_type,
                provider=provider_type,
                target=request.target,
                parameters=request.parameters,
                amount=request.impact_amount,
                currency=request.impact_currency,
            )
            independent.commit(request.idempotency_key, request.target, request.parameters, changes)
            receipt = ActionGatewayReceipt(
                provider=provider_type,
                external_reference="STUDY-" + request.idempotency_key,
                idempotency_key=request.idempotency_key,
                status="completed",
                data={"target": request.target, "synthetic": "true"},
            )
            target.value = dict(independent.objects[request.target])
            insert(
                session,
                "effect",
                request.idempotency_key,
                {
                    "request": payload,
                    "changes": changes,
                    "receipt": receipt.model_dump(mode="json"),
                },
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
        del provider_type
        if adapter_key != "deterministic_demo":
            raise ValueError("Study supports only the synthetic adapter")
        with self.database.session() as session:
            effect = record(session, "effect", request.idempotency_key)
            target = record(session, "target", request.target)
            if effect is None or target is None:
                return ActionLookupResult(
                    found=None,
                    receipt=None,
                    detail="No durable target evidence is available; outcome remains unknown.",
                )
            if effect.value["request"] != request.model_dump(mode="json"):
                return ActionLookupResult(
                    found=None, receipt=None, detail="Payload binding mismatch."
                )
            receipt = ActionGatewayReceipt.model_validate(effect.value["receipt"])
            if external_reference is not None and receipt.external_reference != external_reference:
                return ActionLookupResult(found=None, receipt=None, detail="Reference mismatch.")
            changes: dict[str, str] = effect.value["changes"]
            matches = target.value.get("owner") == request.parameters["recipient"] and all(
                target.value.get(key) == value for key, value in changes.items()
            )
            observed: dict[str, Any] = dict(request.parameters)
            for key in changes.keys() & observed.keys():
                observed[key] = target.value.get(key, "<missing>")
            return ActionLookupResult(
                found=True,
                receipt=receipt,
                detail="Read receipt and independently persisted synthetic target from PostgreSQL.",
                readback=ActionReadback(
                    operation_id=request.idempotency_key,
                    external_reference=receipt.external_reference,
                    action_type=request.action_type,
                    target=request.target,
                    observed_parameters=observed,
                    impact_amount=request.impact_amount,
                    impact_currency=request.impact_currency,
                    observed_at=datetime.now(UTC),
                    effect_count=1,
                    status=VerificationState.VERIFIED if matches else VerificationState.MISMATCH,
                ),
            )

    def check_health(self, *, adapter_key: str, provider_type: str) -> tuple[ConnectionHealth, str]:
        del provider_type
        return (
            (ConnectionHealth.HEALTHY, "Persistent synthetic study target is ready.")
            if (adapter_key == "deterministic_demo" and self.database.is_ready())
            else (ConnectionHealth.UNAVAILABLE, "Persistent study target is unavailable.")
        )
