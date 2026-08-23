import re
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")
    return value


class CaseStatus(StrEnum):
    NEW = "new"
    INVESTIGATING = "investigating"
    INFORMATION_NEEDED = "information_needed"
    NEEDS_REVIEW = "needs_review"
    WAITING_CUSTOMER = "waiting_customer"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CaseCategory(StrEnum):
    BILLING_DISPUTE = "billing_dispute"
    REFUND_REQUEST = "refund_request"
    ACCOUNT_ACCESS = "account_access"
    SERVICE_EXCEPTION = "service_exception"


class CaseUrgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CaseQueueView(StrEnum):
    MINE = "mine"
    ALL = "all"
    UNASSIGNED = "unassigned"
    REVIEW = "review"
    AT_RISK = "at_risk"


class CaseQueueSort(StrEnum):
    PRIORITY = "priority"
    SLA = "sla"
    UPDATED = "updated"


class CaseQueueCursorDirection(StrEnum):
    FORWARD = "forward"
    BACKWARD = "backward"


type CaseCommand = Literal[
    "assign_to_me",
    "start_investigation",
    "request_information",
    "resume_investigation",
    "send_reply",
    "add_note",
    "add_evidence",
    "revise_resolution",
    "save_draft",
    "submit_for_review",
    "escalate",
    "export_audit",
]


class SourceFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class RequestChannel(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"
    WEBHOOK = "webhook"


class CustomerTier(StrEnum):
    STANDARD = "standard"
    VIP = "vip"
    ENTERPRISE = "enterprise"


class BusinessObjectType(StrEnum):
    INVOICE = "invoice"
    PAYMENT = "payment"
    SUBSCRIPTION = "subscription"
    ACCOUNT = "account"
    ORDER = "order"
    DELIVERY = "delivery"
    OTHER = "other"


class MessageChannel(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    PHONE = "phone"
    WEBHOOK = "webhook"
    INTERNAL_NOTE = "internal_note"


class MessageAuthorType(StrEnum):
    CUSTOMER = "customer"
    MEMBER = "member"
    SYSTEM = "system"


class CaseRequestCreate(BaseModel):
    channel: RequestChannel
    customer_message: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    received_at: datetime

    @field_validator("received_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, "received_at")


class CustomerContextCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    tier: CustomerTier
    locale: str = Field(min_length=1, max_length=35)
    contact: str = Field(min_length=1, max_length=320)


class BusinessObjectCreate(BaseModel):
    public_id: str = Field(min_length=1, max_length=64)
    type: BusinessObjectType
    label: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=100)
    source_reference: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=100)
    fields: dict[str, str]
    captured_at: datetime
    freshness: SourceFreshness = SourceFreshness.CURRENT
    checked_at: datetime | None = None

    @field_validator("captured_at", "checked_at")
    @classmethod
    def require_utc(cls, value: datetime | None, info: Any) -> datetime | None:
        return _require_utc(value, info.field_name) if value is not None else None


class BusinessEvidenceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type: BusinessObjectType
    label: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=100)
    source_reference: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=100)
    fields: dict[str, str] = Field(default_factory=dict, max_length=12)

    @field_validator("fields")
    @classmethod
    def normalize_fields(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = raw_key.strip().lower()
            field_value = raw_value.strip()
            if re.fullmatch(r"[a-z][a-z0-9_]{0,49}", key) is None:
                raise ValueError("evidence field names must use lowercase words and underscores")
            if not field_value or len(field_value) > 500:
                raise ValueError("evidence field values must contain 1 to 500 characters")
            if key in normalized:
                raise ValueError("evidence field names must be unique")
            normalized[key] = field_value
        return normalized


class CaseCreate(BaseModel):
    public_id: str = Field(pattern=r"^CS-[A-Z0-9-]+$", max_length=64)
    source_id: str = Field(min_length=1, max_length=200)
    external_reference: str = Field(min_length=1, max_length=200)
    category: CaseCategory
    issue: str = Field(min_length=1, max_length=500)
    status: CaseStatus = CaseStatus.NEW
    urgency: CaseUrgency
    risk: CaseRisk
    due_at: datetime
    impact_amount: Decimal | None = Field(default=None, ge=0)
    impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    source_freshness: SourceFreshness = SourceFreshness.CURRENT
    source_checked_at: datetime | None = None
    request: CaseRequestCreate
    customer: CustomerContextCreate
    business_contexts: list[BusinessObjectCreate] = Field(min_length=1)

    @field_validator("due_at", "source_checked_at")
    @classmethod
    def require_utc(cls, value: datetime | None, info: Any) -> datetime | None:
        return _require_utc(value, info.field_name) if value is not None else None

    @model_validator(mode="after")
    def require_complete_impact(self) -> Self:
        if (self.impact_amount is None) != (self.impact_currency is None):
            raise ValueError("impact_amount and impact_currency must be supplied together")
        return self


class CaseRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    legacy_task_id: UUID | None
    source_id: str
    external_reference: str
    category: CaseCategory
    issue: str
    status: CaseStatus
    owner_id: UUID | None
    urgency: CaseUrgency
    risk: CaseRisk
    due_at: datetime
    impact_amount: Decimal | None
    impact_currency: str | None
    source_freshness: SourceFreshness
    source_checked_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class CaseRequestRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    channel: RequestChannel
    customer_message: str
    summary: str
    received_at: datetime


class CustomerContextRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    case_id: UUID
    customer_id: str
    name: str
    tier: CustomerTier
    locale: str
    contact: str
    captured_at: datetime


class BusinessObjectRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    type: BusinessObjectType
    label: str
    source: str
    source_reference: str
    status: str
    fields: dict[str, Any]
    captured_at: datetime
    source_freshness: SourceFreshness
    source_checked_at: datetime | None
    version: int


class CaseOwnerRecord(BaseModel):
    id: UUID
    public_id: str
    name: str


class ConversationThreadRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    version: int
    updated_at: datetime


class ConversationMessageRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    thread_id: UUID
    author_type: MessageAuthorType
    author_id: str | None
    author_name: str
    channel: MessageChannel
    body: str
    internal: bool
    source_reference: str | None
    version: int
    created_at: datetime


class ResponseDraftRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    public_id: str
    organization_id: UUID
    case_id: UUID
    subject: str
    body: str
    status: str
    version: int
    updated_at: datetime


class CaseActivityRecord(BaseModel):
    id: UUID
    event_type: str
    actor_id: str | None
    summary: str
    occurred_at: datetime


class CaseListItemRecord(BaseModel):
    case: CaseRecord
    customer: CustomerContextRecord
    owner: CaseOwnerRecord | None


class CaseQueueSummaryRecord(BaseModel):
    total: int = Field(ge=0)
    attention: int = Field(ge=0)
    review: int = Field(ge=0)
    sla_at_risk: int = Field(ge=0)
    unassigned: int = Field(ge=0)


class CaseQueuePosition(BaseModel):
    ordered_at: datetime
    public_id: str = Field(min_length=1, max_length=64)
    risk_rank: int | None = Field(default=None, ge=0, le=2)

    @field_validator("ordered_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, "ordered_at")


class CaseQueueCursorRecord(BaseModel):
    direction: CaseQueueCursorDirection
    offset: int = Field(ge=0)
    snapshot_at: datetime
    position: CaseQueuePosition

    @field_validator("snapshot_at")
    @classmethod
    def require_snapshot_utc(cls, value: datetime) -> datetime:
        return _require_utc(value, "snapshot_at")


class CaseListPageRecord(BaseModel):
    items: list[CaseListItemRecord]
    next_cursor: CaseQueueCursorRecord | None
    previous_cursor: CaseQueueCursorRecord | None
    total: int
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    summary_scope: Literal["organization"] = "organization"
    summary: CaseQueueSummaryRecord = Field(
        default_factory=lambda: CaseQueueSummaryRecord(
            total=0,
            attention=0,
            review=0,
            sla_at_risk=0,
            unassigned=0,
        )
    )


class CaseHistoryPosition(BaseModel):
    occurred_at: datetime
    tie_breaker: str = Field(min_length=1, max_length=128)


class CaseCollectionWindowRecord(BaseModel):
    returned: int = Field(ge=0)
    total: int = Field(ge=0)
    has_more: bool
    next_position: CaseHistoryPosition | None = None

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.returned > self.total:
            raise ValueError("returned collection items cannot exceed the total")
        if self.has_more != (self.returned < self.total):
            raise ValueError("has_more must match the returned and total collection counts")
        if not self.has_more and self.next_position is not None:
            raise ValueError("a continuation position requires more collection items")
        return self


class CaseWorkspaceCollectionsRecord(BaseModel):
    business_contexts: CaseCollectionWindowRecord
    messages: CaseCollectionWindowRecord
    activity: CaseCollectionWindowRecord


class ConversationMessagePageRecord(BaseModel):
    items: list[ConversationMessageRecord]
    total: int = Field(ge=0)
    next_position: CaseHistoryPosition | None


class CaseActivityPageRecord(BaseModel):
    items: list[CaseActivityRecord]
    total: int = Field(ge=0)
    next_position: CaseHistoryPosition | None


class CaseWorkspaceRecord(BaseModel):
    case: CaseRecord
    request: CaseRequestRecord
    customer: CustomerContextRecord
    business_contexts: list[BusinessObjectRecord]
    owner: CaseOwnerRecord | None
    thread: ConversationThreadRecord
    messages: list[ConversationMessageRecord]
    draft: ResponseDraftRecord | None
    activity: list[CaseActivityRecord]
    collections: CaseWorkspaceCollectionsRecord


CASE_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.NEW: frozenset({CaseStatus.INVESTIGATING, CaseStatus.INFORMATION_NEEDED}),
    CaseStatus.INVESTIGATING: frozenset(
        {
            CaseStatus.INFORMATION_NEEDED,
            CaseStatus.NEEDS_REVIEW,
            CaseStatus.WAITING_CUSTOMER,
            CaseStatus.IN_PROGRESS,
        }
    ),
    CaseStatus.INFORMATION_NEEDED: frozenset(
        {CaseStatus.INVESTIGATING, CaseStatus.WAITING_CUSTOMER}
    ),
    CaseStatus.NEEDS_REVIEW: frozenset({CaseStatus.IN_PROGRESS, CaseStatus.INVESTIGATING}),
    CaseStatus.WAITING_CUSTOMER: frozenset(
        {CaseStatus.INVESTIGATING, CaseStatus.INFORMATION_NEEDED}
    ),
    CaseStatus.IN_PROGRESS: frozenset(
        {CaseStatus.COMPLETED, CaseStatus.INFORMATION_NEEDED, CaseStatus.NEEDS_REVIEW}
    ),
    CaseStatus.COMPLETED: frozenset(),
}


class InvalidCaseTransition(ValueError):
    pass


class CaseNotFound(LookupError):
    pass


class CaseConcurrencyConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The case changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


class DraftConcurrencyConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The response draft changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version


class BusinessEvidenceConflict(RuntimeError):
    pass


class BusinessEvidenceNotAllowed(RuntimeError):
    pass


class CaseActorNotAssignable(LookupError):
    pass


class CaseSeedConflict(RuntimeError):
    pass


def require_case_transition(current: CaseStatus, target: CaseStatus) -> None:
    if target not in CASE_TRANSITIONS[current]:
        raise InvalidCaseTransition(f"Case cannot move from {current.value} to {target.value}.")
