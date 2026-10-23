from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.cases import CaseNotFound
from app.domain.identity import ActorContext, Permission
from app.domain.resolution import (
    ActionReadback,
    LifecycleConflict,
    VerificationState,
    verify_readback,
)
from app.persistence.models import (
    AuditEventModel,
    CaseActionModel,
    CaseActionReceiptModel,
    CaseActionReconciliationModel,
    CaseModel,
    MembershipModel,
    OrganizationModel,
)
from app.persistence.models.base import utc_now
from app.persistence.models.resolution import CaseResolutionEventModel as Event
from app.security.authorization import require_permission
from app.services.lifecycle_telemetry import LifecycleSpan, emit_span


class ResolutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def case(self, actor: ActorContext, case_id: str, *, lock: bool = True) -> CaseModel:
        query = (
            select(CaseModel)
            .join(OrganizationModel, OrganizationModel.id == CaseModel.organization_id)
            .where(
                OrganizationModel.public_id == actor.organization_id, CaseModel.public_id == case_id
            )
        )
        if lock:
            query = query.with_for_update(of=CaseModel)
        case = self.session.scalar(query)
        if case is None:
            raise CaseNotFound("The case was not found.")
        return case

    def events(self, case: CaseModel) -> list[Event]:
        return list(
            self.session.scalars(
                select(Event)
                .where(
                    Event.organization_id == case.organization_id,
                    Event.case_id == case.id,
                )
                .order_by(Event.occurred_at, Event.id)
            )
        )

    def controls(
        self, actor: ActorContext, case: CaseModel, history: list[Event]
    ) -> dict[str, Any]:
        """Read-only projection; the command rechecks every condition in its transaction."""
        blocker = None
        proofs: list[str] = []
        if case.status != "in_progress":
            blocker = "Complete and verify the required actions before closing this case."
        else:
            try:
                proofs = self.closure_proofs(case, history)
            except LifecycleConflict as exc:
                blocker = str(exc)
        available = []
        if Permission.CASE_MANAGE in actor.permissions:
            if case.status == "completed":
                available.append("reopened")
            elif blocker is None and Permission.REVIEW_DECIDE in actor.permissions:
                available.append("completed")
        actions = self.session.scalars(
            select(CaseActionModel).where(
                CaseActionModel.organization_id == case.organization_id,
                CaseActionModel.case_id == case.id,
            )
        ).all()
        return {
            "closure": {
                "eligible": blocker is None,
                "blocker": blocker,
                "verification_ids": proofs,
            },
            "available_commands": available,
            "actions": [{"id": a.public_id, "status": a.status} for a in actions],
        }

    def append(
        self,
        case: CaseModel,
        *,
        kind: str,
        actor_id: str,
        command_id: str,
        correlation_id: str,
        data: dict[str, Any],
        previous: UUID | None = None,
    ) -> Event:
        event = Event(
            id=uuid4(),
            organization_id=case.organization_id,
            case_id=case.id,
            kind=kind,
            actor_id=actor_id,
            command_id=command_id,
            correlation_id=correlation_id,
            data=data,
            previous_event_id=previous,
            occurred_at=utc_now(),
        )
        self.session.add(
            AuditEventModel(
                organization_id=case.organization_id,
                event_type=f"case.resolution_{kind}",
                actor_type="system" if actor_id == "system" else "member",
                actor_id=actor_id,
                subject_type="case",
                subject_id=case.public_id,
                summary=f"Case lifecycle: {kind}.",
                data={
                    "resolution_event_id": str(event.id),
                    "previous_event_id": str(previous) if previous else None,
                },
                correlation_id=correlation_id,
                occurred_at=event.occurred_at,
            )
        )
        self.session.add(event)
        self.session.flush()
        return event

    def command(
        self,
        *,
        actor: ActorContext,
        case_id: str,
        expected_version: int,
        command_id: str,
        kind: str,
        reason: str,
        reference: str | None,
        correlation_id: str,
    ) -> Event:
        require_permission(actor, Permission.CASE_MANAGE)
        if kind in {"completed", "escalation_acknowledged"}:
            require_permission(actor, Permission.REVIEW_DECIDE)
        case = self.case(actor, case_id)
        history = self.events(case)
        replay = next((e for e in history if e.command_id == command_id), None)
        request = {"reason": reason, "reference": reference, "expected_version": expected_version}
        if replay is not None:
            if (
                replay.kind != kind
                or replay.actor_id != actor.actor_id
                or replay.data.get("request") != request
            ):
                raise LifecycleConflict("Idempotency key already used for another command.")
            return replay
        if case.version != expected_version:
            raise LifecycleConflict("Case version changed; reload before continuing.")
        previous = None
        details: dict[str, Any] = {"request": request, "case_version": case.version}
        if kind == "completed":
            if case.status != "in_progress":
                raise LifecycleConflict("Only an in-progress case can be closed.")
            if not reference:
                raise LifecycleConflict("A delivered customer communication reference is required.")
            proofs = self.closure_proofs(case, history)
            details.update(
                verification_ids=proofs,
                communication_reference=reference,
                communication_attestation_by=actor.actor_id,
                automation=False,
            )
            details["end_to_end_elapsed_ms"] = (utc_now() - case.created_at).total_seconds() * 1000
            case.status = "completed"
        elif kind == "reopened":
            if case.status != "completed":
                raise LifecycleConflict("Only a completed case can be reopened.")
            completion = next((e for e in reversed(history) if e.kind == "completed"), None)
            previous = completion.id if completion else None
            details["legacy_completion"] = completion is None
            if not reference:
                raise LifecycleConflict("Reopen requires a new evidence reference.")
            case.status = "investigating"
        elif kind == "escalation_routed":
            if case.status == "completed":
                raise LifecycleConflict("Reopen a completed case before escalation.")
            member = self.session.scalar(
                select(MembershipModel).where(
                    MembershipModel.organization_id == case.organization_id,
                    MembershipModel.public_id == reference,
                    MembershipModel.status == "active",
                    MembershipModel.role.in_(["supervisor", "administrator"]),
                )
            )
            if member is None:
                raise LifecycleConflict(
                    "Choose an active supervisor or administrator in this tenant."
                )
            case.owner_id = member.id
            details["destination_member_id"] = member.public_id
            details["queue"] = {
                "billing_dispute": "billing_specialists",
                "refund_request": "refund_specialists",
                "account_access": "account_recovery_specialists",
                "service_exception": "service_specialists",
            }[case.category]
        elif kind == "escalation_acknowledged":
            route = next((e for e in reversed(history) if e.kind == "escalation_routed"), None)
            if route is None or reference != str(route.id):
                raise LifecycleConflict("Acknowledgement must reference the latest routing event.")
            assigned = self.session.scalar(
                select(MembershipModel).where(
                    MembershipModel.organization_id == case.organization_id,
                    MembershipModel.id == case.owner_id,
                    MembershipModel.status == "active",
                    MembershipModel.public_id == route.data["destination_member_id"],
                    or_(
                        MembershipModel.public_id == actor.actor_id,
                        MembershipModel.subject_id == actor.actor_id,
                    ),
                )
            )
            if assigned is None:
                raise LifecycleConflict("Only the assigned active recipient can acknowledge.")
            if any(e.kind == kind and e.previous_event_id == route.id for e in history):
                raise LifecycleConflict("This escalation is already acknowledged.")
            previous = route.id
            details["manual_wait_ms"] = (utc_now() - route.occurred_at).total_seconds() * 1000
        else:
            raise LifecycleConflict("Unsupported lifecycle command.")
        for field, stage in (
            ("end_to_end_elapsed_ms", "end_to_end"),
            ("manual_wait_ms", "manual_wait"),
        ):
            if field in details:
                emit_span(
                    LifecycleSpan(
                        correlation_id=correlation_id,
                        subject_id=case.public_id,
                        stage=stage,
                        duration_ms=details[field],
                        outcome="completed",
                    )
                )
        case.version += 1
        case.updated_at = utc_now()
        return self.append(
            case,
            kind=kind,
            actor_id=actor.actor_id,
            command_id=command_id,
            correlation_id=correlation_id,
            data=details,
            previous=previous,
        )

    def closure_proofs(self, case: CaseModel, history: list[Event]) -> list[str]:
        actions = list(
            self.session.scalars(
                select(CaseActionModel).where(
                    CaseActionModel.organization_id == case.organization_id,
                    CaseActionModel.case_id == case.id,
                )
            )
        )
        if not actions:
            raise LifecycleConflict(
                "No verified action resolution exists; explanation-only closure is not enabled."
            )
        from app.persistence.actions._base import ActionRepositoryBase

        authority = ActionRepositoryBase(self.session)
        proofs = []
        for action in actions:
            event = next(
                (
                    e
                    for e in reversed(history)
                    if e.kind == "action_verified" and e.data.get("action_id") == action.public_id
                ),
                None,
            )
            if action.status != "completed" or event is None:
                raise LifecycleConflict(
                    "Every required action must have a verified downstream outcome."
                )
            if (
                event.data.get("case_version") != case.version
                or authority._authority_blocker(action, now=utc_now(), for_closure=True) is not None
            ):
                raise LifecycleConflict(
                    "Resolution authority or case evidence changed; refresh review."
                )
            # Never close on a proof superseded by a later failure/unknown read-back or reopen.
            if any(
                e.occurred_at > event.occurred_at
                and (
                    e.kind == "reopened"
                    or (e.kind == "action_observed" and e.data.get("action_id") == action.public_id)
                )
                for e in history
            ):
                raise LifecycleConflict("Outcome verification must be refreshed.")
            running = self.session.scalar(
                select(CaseActionReconciliationModel.id).where(
                    CaseActionReconciliationModel.action_id == action.id,
                    CaseActionReconciliationModel.outcome == "running",
                )
            )
            receipt = self.session.scalar(
                select(CaseActionReceiptModel).where(
                    CaseActionReceiptModel.action_id == action.id,
                )
            )
            proof_data = event.data.get("proof")
            if running is not None or receipt is None or proof_data is None:
                raise LifecycleConflict("A current target read-back is required before closure.")
            state = verify_readback(
                proof=ActionReadback.model_validate(proof_data),
                operation_id=action.idempotency_key,
                external_reference=receipt.external_reference,
                action_type=action.type,
                target=action.target,
                parameters=action.typed_parameters,
                impact_amount=action.impact_amount,
                impact_currency=action.impact_currency,
                now=utc_now(),
            )
            if state is not VerificationState.VERIFIED:
                raise LifecycleConflict(
                    "Outcome verification is stale or does not match the action."
                )
            proofs.append(str(event.id))
        return proofs
