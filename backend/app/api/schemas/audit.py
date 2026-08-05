from typing import Any, Literal

from pydantic import Field

from app.api.schemas.common import ApiSchema, DataResponse, PublicId, UtcDateTime


class AuditActorResponse(ApiSchema):
    id: PublicId
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["member", "service", "system", "unknown"]


class AuditEventResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    case_id: PublicId | None
    actor: AuditActorResponse
    event_type: str = Field(min_length=1, max_length=100)
    subject_type: str = Field(min_length=1, max_length=100)
    subject_id: PublicId
    summary: str = Field(min_length=1, max_length=500)
    correlation_id: str = Field(min_length=1, max_length=128)
    occurred_at: UtcDateTime
    details: dict[str, Any]


class CaseGovernanceResponse(ApiSchema):
    status: str = Field(min_length=1, max_length=32)
    conversation_retention_until: UtcDateTime | None
    audit_retention_until: UtcDateTime | None
    legal_hold: bool
    redacted_at: UtcDateTime | None
    policy_version: int | None = Field(default=None, ge=1)


class CaseAuditExportResponse(ApiSchema):
    case_id: PublicId
    organization_id: PublicId
    source_id: str = Field(min_length=1, max_length=200)
    external_reference: str = Field(min_length=1, max_length=200)
    legacy_task_id: PublicId | None
    generated_at: UtcDateTime
    generated_by: PublicId
    governance: CaseGovernanceResponse | None
    events: list[AuditEventResponse]


class CaseAuditExportEnvelope(DataResponse[CaseAuditExportResponse]):
    pass
