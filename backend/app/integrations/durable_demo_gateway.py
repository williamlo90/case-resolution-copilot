"""Persistent synthetic target; deliberately separate from product action receipts."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.actions import ActionSideEffectState
from app.domain.connections import ConnectionHealth
from app.domain.resolution import ActionReadback, VerificationState
from app.integrations.action_gateway import (
    ActionGateway,
    ActionGatewayError,
    ActionGatewayReceipt,
    ActionGatewayRequest,
    ActionLookupResult,
    DeterministicActionGateway,
)
from app.integrations.controlled_target import ControlledTarget
from app.persistence.database import Database
from app.persistence.models import AuditEventModel


class DurableDemoGateway(ActionGateway):
    def __init__(
        self, database: Database, organization_id: UUID, *, timeout_after_commit: bool = False
    ) -> None:
        self.database = database
        self.organization_id = organization_id
        self.timeout_after_commit = timeout_after_commit

    def _events(self, session: Session) -> list[AuditEventModel]:
        return list(
            session.scalars(
                select(AuditEventModel)
                .where(
                    AuditEventModel.organization_id == self.organization_id,
                    AuditEventModel.event_type.in_(
                        ["demo.target_initialized", "demo.target_effect"]
                    ),
                )
                .order_by(AuditEventModel.occurred_at, AuditEventModel.id)
            )
        )

    def _target(self, session: Session) -> tuple[ControlledTarget, list[dict[str, Any]]]:
        events = self._events(session)
        initial = [e for e in events if e.event_type == "demo.target_initialized"]
        if len(initial) != 1:
            raise ValueError("This tenant is not an initialized synthetic demo target")
        target = ControlledTarget(initial[0].data["objects"])
        effects = [e.data for e in events if e.event_type == "demo.target_effect"]
        for effect in effects:
            request = ActionGatewayRequest.model_validate(effect["request"])
            target.commit(
                request.idempotency_key, request.target, request.parameters, effect["changes"]
            )
        return target, effects

    def inspect(self) -> dict[str, Any]:
        with self.database.session() as session:
            target, effects = self._target(session)
            return {
                "objects": target.objects,
                "effect_count": len(effects),
                "operations": [
                    {
                        "operation_id": e["request"]["idempotency_key"],
                        "target": e["request"]["target"],
                        "changes": e["changes"],
                    }
                    for e in effects
                ],
                "storage": "database_event_ledger",
            }

    def execute(
        self, *, adapter_key: str, provider_type: str, request: ActionGatewayRequest
    ) -> ActionGatewayReceipt:
        DeterministicActionGateway._require_demo_adapter(adapter_key)
        with self.database.session() as session:
            # Session-level target lock also works when Vercel uses multiple workers.
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"v2-demo-target:{self.organization_id}"},
            )
            target, effects = self._target(session)
            for effect in effects:
                original = ActionGatewayRequest.model_validate(effect["request"])
                if original.idempotency_key == request.idempotency_key:
                    if original != request:
                        raise self._rejected("idempotency_payload_conflict")
                    return ActionGatewayReceipt.model_validate(effect["receipt"]).model_copy(
                        update={"duplicate": True}
                    )
            if effects:
                raise self._rejected("demo_target_already_changed")
            try:
                if request.action_type != "refund_course_fee":
                    raise ValueError("Only the registered synthetic course refund is supported")
                changes = target.prepare(
                    action_type=request.action_type,
                    provider=provider_type,
                    target=request.target,
                    parameters=request.parameters,
                    amount=request.impact_amount,
                    currency=request.impact_currency,
                )
            except (KeyError, ValueError) as exc:
                raise self._rejected("invalid_controlled_target") from exc
            receipt = DeterministicActionGateway._receipt(provider_type, request)
            session.add(
                AuditEventModel(
                    organization_id=self.organization_id,
                    event_type="demo.target_effect",
                    actor_type="system",
                    subject_type="synthetic_target",
                    subject_id=request.target,
                    summary="One synthetic target change committed; no external payment.",
                    data={
                        "request": request.model_dump(mode="json"),
                        "changes": changes,
                        "receipt": receipt.model_dump(mode="json"),
                    },
                    correlation_id=request.idempotency_key,
                )
            )
        # Commit must finish before simulating loss of the response.
        if self.timeout_after_commit:
            raise ActionGatewayError(
                "Synthetic target committed, but its response timed out. "
                "Reconcile before retrying.",
                code="target_timeout_after_acceptance",
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
        DeterministicActionGateway._require_demo_adapter(adapter_key)
        with self.database.session() as session:
            target, effects = self._target(session)
            for effect in effects:
                original = ActionGatewayRequest.model_validate(effect["request"])
                if original.idempotency_key != request.idempotency_key:
                    continue
                receipt = ActionGatewayReceipt.model_validate(effect["receipt"])
                if (
                    original != request
                    or receipt.provider != provider_type
                    or external_reference not in {None, receipt.external_reference}
                ):
                    return ActionLookupResult(
                        found=None, receipt=None, detail="Operation identity or payload mismatch."
                    )
                observed, matches = target.readback(request.idempotency_key)
                return ActionLookupResult(
                    found=True,
                    receipt=receipt,
                    detail="Fresh read of the durable synthetic target and its effect ledger.",
                    readback=ActionReadback(
                        operation_id=original.idempotency_key,
                        external_reference=receipt.external_reference,
                        action_type=original.action_type,
                        target=original.target,
                        observed_parameters=observed,
                        impact_amount=original.impact_amount,
                        impact_currency=original.impact_currency,
                        status=VerificationState.VERIFIED
                        if matches
                        else VerificationState.MISMATCH,
                        observed_at=datetime.now(UTC),
                        effect_count=len(effects),
                    ),
                )
        return ActionLookupResult(found=False, receipt=None, detail="No synthetic effect found.")

    def check_health(self, *, adapter_key: str, provider_type: str) -> tuple[ConnectionHealth, str]:
        DeterministicActionGateway._require_demo_adapter(adapter_key)
        return ConnectionHealth.HEALTHY, "Durable synthetic target; no external provider."

    @staticmethod
    def _rejected(code: str) -> ActionGatewayError:
        return ActionGatewayError(
            "Synthetic target rejected the operation before any additional change.",
            code=code,
            side_effect_state=ActionSideEffectState.NONE,
            retryable=False,
        )
