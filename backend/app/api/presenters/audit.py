from app.api.schemas.audit import (
    AuditActorResponse,
    AuditEventResponse,
    CaseAuditExportResponse,
    CaseGovernanceResponse,
)
from app.domain.audit import CaseAuditExportRecord


def present_case_audit_export(
    record: CaseAuditExportRecord,
) -> CaseAuditExportResponse:
    return CaseAuditExportResponse(
        case_id=record.case_public_id,
        organization_id=record.organization_public_id,
        source_id=record.source_id,
        external_reference=record.external_reference,
        legacy_task_id=record.legacy_task_id,
        generated_at=record.generated_at,
        generated_by=record.generated_by,
        governance=(
            CaseGovernanceResponse(
                status=record.governance.status,
                conversation_retention_until=(
                    record.governance.conversation_retention_until
                ),
                audit_retention_until=record.governance.audit_retention_until,
                legal_hold=record.governance.legal_hold,
                redacted_at=record.governance.redacted_at,
                policy_version=record.governance.policy_version,
            )
            if record.governance is not None
            else None
        ),
        events=[
            AuditEventResponse(
                id=str(event.id),
                organization_id=event.organization_public_id,
                case_id=event.case_public_id,
                actor=AuditActorResponse(
                    id=event.actor.id,
                    name=event.actor.name,
                    kind=event.actor.kind,
                ),
                event_type=event.event_type,
                subject_type=event.subject_type,
                subject_id=event.subject_id,
                summary=event.summary,
                correlation_id=event.correlation_id,
                occurred_at=event.occurred_at,
                details=event.details,
            )
            for event in record.events
        ],
    )
