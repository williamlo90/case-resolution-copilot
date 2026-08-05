from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.cases import (
    BusinessObjectCreate,
    BusinessObjectType,
    CaseCategory,
    CaseCreate,
    CaseRequestCreate,
    CaseRisk,
    CaseUrgency,
    CustomerContextCreate,
    CustomerTier,
    RequestChannel,
    SourceFreshness,
)


class _WebhookModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseWebhookRequest(_WebhookModel):
    channel: RequestChannel
    customer_message: str = Field(min_length=1, max_length=20_000)
    summary: str = Field(min_length=1, max_length=1000)
    received_at: datetime


class CaseWebhookCustomer(_WebhookModel):
    customer_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    tier: CustomerTier = CustomerTier.STANDARD
    locale: str = Field(default="en-US", min_length=1, max_length=35)
    contact: str = Field(min_length=1, max_length=320)


class CaseWebhookBusinessObject(_WebhookModel):
    type: BusinessObjectType
    label: str = Field(min_length=1, max_length=300)
    source: str = Field(min_length=1, max_length=100)
    source_reference: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=100)
    fields: dict[str, str] = Field(max_length=50)
    captured_at: datetime
    freshness: SourceFreshness = SourceFreshness.CURRENT
    checked_at: datetime | None = None

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not key or len(key) > 100 or len(item) > 2000 for key, item in value.items()):
            raise ValueError("context fields exceed the supported size")
        return value


class SignedCaseWebhookEvent(_WebhookModel):
    event_id: str = Field(
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    external_reference: str = Field(min_length=1, max_length=200)
    category: CaseCategory
    issue: str = Field(min_length=1, max_length=500)
    urgency: CaseUrgency
    risk: CaseRisk
    due_at: datetime
    impact_amount: Decimal | None = Field(default=None, ge=0)
    impact_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    source_freshness: SourceFreshness = SourceFreshness.CURRENT
    source_checked_at: datetime | None = None
    request: CaseWebhookRequest
    customer: CaseWebhookCustomer
    business_contexts: list[CaseWebhookBusinessObject] = Field(
        min_length=1,
        max_length=20,
    )

    def to_case_create(self, *, organization_id: str) -> CaseCreate:
        case_token = _token(organization_id, self.event_id)
        return CaseCreate(
            public_id=f"CS-WH-{case_token}",
            source_id=f"signed-webhook:{self.event_id}",
            external_reference=self.external_reference,
            category=self.category,
            issue=self.issue,
            urgency=self.urgency,
            risk=self.risk,
            due_at=self.due_at,
            impact_amount=self.impact_amount,
            impact_currency=self.impact_currency,
            source_freshness=self.source_freshness,
            source_checked_at=self.source_checked_at,
            request=CaseRequestCreate.model_validate(self.request.model_dump()),
            customer=CustomerContextCreate.model_validate(self.customer.model_dump()),
            business_contexts=[
                BusinessObjectCreate(
                    public_id=f"CTX-WH-{case_token[:12]}-{index:02d}",
                    type=context.type,
                    label=context.label,
                    source=context.source,
                    source_reference=context.source_reference,
                    status=context.status,
                    fields=context.fields,
                    captured_at=context.captured_at,
                    freshness=context.freshness,
                    checked_at=context.checked_at,
                )
                for index, context in enumerate(self.business_contexts, start=1)
            ],
        )


def _token(*parts: Any) -> str:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return sha256(payload).hexdigest()[:20].upper()
