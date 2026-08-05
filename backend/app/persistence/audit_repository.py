from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.domain.audit import (
    CaseAuditActorRecord,
    CaseAuditEventRecord,
    CaseAuditExportRecord,
    CaseAuditNotFound,
    CaseGovernanceRecord,
)
from app.domain.identity import ActorMembershipNotFound
from app.persistence.models import (
    AuditEventModel,
    CaseActionModel,
    CaseDataGovernanceModel,
    CaseModel,
    CaseProposalModel,
    CaseReviewModel,
    MembershipModel,
    OrganizationModel,
    TaskModel,
)
from app.tools.redaction import redact


class CaseAuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def export(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        correlation_id: str,
    ) -> CaseAuditExportRecord:
        organization = self._session.scalar(
            select(OrganizationModel).where(
                OrganizationModel.public_id == organization_public_id
            )
        )
        if organization is None:
            raise CaseAuditNotFound("The case audit record was not found.")
        case = self._session.scalar(
            select(CaseModel).where(
                CaseModel.organization_id == organization.id,
                CaseModel.public_id == case_public_id,
            )
        )
        if case is None:
            raise CaseAuditNotFound("The case audit record was not found.")
        member = self._session.scalar(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization.id,
                MembershipModel.status == "active",
                or_(
                    MembershipModel.public_id == actor_id,
                    MembershipModel.subject_id == actor_id,
                ),
            )
        )
        if member is None:
            raise ActorMembershipNotFound(
                "An active organization membership is required to export audit records."
            )

        generated_at = datetime.now(UTC)
        export_event = AuditEventModel(
            organization_id=organization.id,
            task_id=case.legacy_task_id,
            run_id=None,
            event_type="case.audit_exported",
            actor_type="member",
            actor_id=member.public_id,
            subject_type="case",
            subject_id=case.public_id,
            summary="Case audit record exported.",
            data={"case_id": case.public_id},
            correlation_id=correlation_id,
            occurred_at=generated_at,
        )
        self._session.add(export_event)
        self._session.flush()

        review_ids = list(
            self._session.scalars(
                select(CaseReviewModel.public_id).where(
                    CaseReviewModel.organization_id == organization.id,
                    CaseReviewModel.case_id == case.id,
                )
            )
        )
        action_ids = list(
            self._session.scalars(
                select(CaseActionModel.public_id).where(
                    CaseActionModel.organization_id == organization.id,
                    CaseActionModel.case_id == case.id,
                )
            )
        )
        proposal_ids = list(
            self._session.scalars(
                select(CaseProposalModel.public_id).where(
                    CaseProposalModel.organization_id == organization.id,
                    CaseProposalModel.case_id == case.id,
                )
            )
        )
        subject_conditions = [
            and_(
                AuditEventModel.subject_type == "case",
                AuditEventModel.subject_id == case.public_id,
            )
        ]
        if review_ids:
            subject_conditions.append(
                and_(
                    AuditEventModel.subject_type == "review",
                    AuditEventModel.subject_id.in_(review_ids),
                )
            )
        if action_ids:
            subject_conditions.append(
                and_(
                    AuditEventModel.subject_type == "action",
                    AuditEventModel.subject_id.in_(action_ids),
                )
            )
        if proposal_ids:
            subject_conditions.append(
                and_(
                    AuditEventModel.subject_type == "proposal",
                    AuditEventModel.subject_id.in_(proposal_ids),
                )
            )

        scope_conditions = [
            and_(
                AuditEventModel.organization_id == organization.id,
                or_(*subject_conditions),
            )
        ]
        if case.legacy_task_id is not None:
            scope_conditions.append(
                and_(
                    AuditEventModel.organization_id == organization.id,
                    AuditEventModel.task_id == case.legacy_task_id,
                )
            )
        events = list(
            self._session.scalars(
                select(AuditEventModel)
                .where(or_(*scope_conditions))
                .order_by(AuditEventModel.occurred_at, AuditEventModel.id)
            )
        )
        actors = self._actor_names(
            organization_id=organization.id,
            actor_ids={event.actor_id for event in events if event.actor_id},
        )
        governance_model = self._session.scalar(
            select(CaseDataGovernanceModel).where(
                CaseDataGovernanceModel.organization_id == organization.id,
                CaseDataGovernanceModel.case_id == case.id,
            )
        )
        legacy_reference = None
        if case.legacy_task_id is not None:
            legacy_reference = self._session.scalar(
                select(TaskModel.public_id).where(TaskModel.id == case.legacy_task_id)
            )
        return CaseAuditExportRecord(
            case_public_id=case.public_id,
            organization_public_id=organization.public_id,
            source_id=case.source_id,
            external_reference=case.external_reference,
            legacy_task_id=legacy_reference,
            generated_at=generated_at,
            generated_by=member.public_id,
            governance=(
                CaseGovernanceRecord(
                    status=governance_model.redaction_status,
                    conversation_retention_until=(
                        governance_model.conversation_retention_until
                    ),
                    audit_retention_until=governance_model.audit_retention_until,
                    legal_hold=governance_model.legal_hold,
                    redacted_at=governance_model.redacted_at,
                    policy_version=governance_model.retention_policy_version,
                )
                if governance_model is not None
                else None
            ),
            events=[
                CaseAuditEventRecord(
                    id=event.id,
                    organization_public_id=organization.public_id,
                    case_public_id=case.public_id,
                    actor=_audit_actor(event, actors),
                    event_type=event.event_type,
                    subject_type=event.subject_type or "case",
                    subject_id=event.subject_id or case.public_id,
                    summary=event.summary or _default_summary(event.event_type),
                    correlation_id=event.correlation_id,
                    occurred_at=event.occurred_at,
                    details=redact(event.data),
                )
                for event in events
            ],
        )

    def _actor_names(
        self,
        *,
        organization_id: UUID,
        actor_ids: set[str],
    ) -> dict[str, str]:
        if not actor_ids:
            return {}
        members = self._session.scalars(
            select(MembershipModel).where(
                MembershipModel.organization_id == organization_id,
                or_(
                    MembershipModel.public_id.in_(actor_ids),
                    MembershipModel.subject_id.in_(actor_ids),
                ),
            )
        )
        names: dict[str, str] = {}
        for member in members:
            names[member.public_id] = member.name
            names[member.subject_id] = member.name
        return names


def _audit_actor(
    event: AuditEventModel,
    names: dict[str, str],
) -> CaseAuditActorRecord:
    actor_id = event.actor_id or "unavailable"
    if event.actor_type in {"member", "human"}:
        name = names.get(actor_id, "Member unavailable")
        kind = "member"
    elif event.actor_type == "service":
        name = "Service"
        kind = "service"
    elif event.actor_type == "system":
        name = "System"
        kind = "system"
    else:
        name = "Actor unavailable"
        kind = "unknown"
    return CaseAuditActorRecord(
        id=actor_id,
        name=name,
        kind=kind,
    )


def _default_summary(event_type: str) -> str:
    return event_type.replace(".", " ").replace("_", " ").capitalize()
