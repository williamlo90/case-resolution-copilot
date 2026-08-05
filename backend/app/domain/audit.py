from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID | None
    run_id: UUID | None
    event_type: str
    actor_type: str
    data: dict[str, Any]
    correlation_id: str
    occurred_at: datetime


class CaseAuditActorRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: Literal["member", "service", "system", "unknown"]


class CaseAuditEventRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_public_id: str
    case_public_id: str
    actor: CaseAuditActorRecord
    event_type: str
    subject_type: str
    subject_id: str
    summary: str
    correlation_id: str
    occurred_at: datetime
    details: dict[str, Any]


class CaseGovernanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    conversation_retention_until: datetime | None
    audit_retention_until: datetime | None
    legal_hold: bool
    redacted_at: datetime | None
    policy_version: int | None


class CaseAuditExportRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_public_id: str
    organization_public_id: str
    source_id: str
    external_reference: str
    legacy_task_id: str | None
    generated_at: datetime
    generated_by: str
    governance: CaseGovernanceRecord | None
    events: list[CaseAuditEventRecord]


class CaseAuditNotFound(LookupError):
    pass
