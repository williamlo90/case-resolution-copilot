from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProviderScenario(StrEnum):
    SUCCESS = "success"
    REJECT_BEFORE_SIDE_EFFECT = "reject_before_side_effect"
    TIMEOUT_BEFORE_SEND = "timeout_before_send"
    TIMEOUT_AFTER_ACCEPTANCE = "timeout_after_acceptance"
    DELAYED_POSTCONDITION = "delayed_postcondition"


class SideEffectState(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    NONE = "none"
    CONFIRMED = "confirmed"
    POSSIBLE = "possible"


class ActionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class IdentifierInput(StrictToolModel):
    id: str = Field(min_length=3, max_length=64)


class CaseOutput(StrictToolModel):
    case_id: str
    account_id: str
    status: str
    category: str
    customer_message: str


class CustomerProfileOutput(StrictToolModel):
    customer_id: str
    name: str
    tier: str
    locale: str
    contact: str


class AccountSnapshotOutput(StrictToolModel):
    account_id: str
    customer_id: str
    plan: str
    status: str
    balance: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class EntitlementInput(StrictToolModel):
    account_id: str = Field(min_length=3, max_length=64)
    case_category: str = Field(min_length=3, max_length=64)
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class EntitlementOutput(StrictToolModel):
    eligible: bool
    maximum_credit: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    reason_code: str


class DraftInput(StrictToolModel):
    case_id: str = Field(min_length=3, max_length=64)
    body: str = Field(min_length=8, max_length=4000)


class DraftOutput(StrictToolModel):
    draft_id: str
    case_id: str
    body: str
    status: str = "draft"


class CreateCreditInput(StrictToolModel):
    account_id: str = Field(min_length=3, max_length=64)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    reason_code: str = Field(min_length=3, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=128)
    scenario: ProviderScenario = ProviderScenario.SUCCESS


class ActionReceiptOutput(StrictToolModel):
    external_reference: str
    resource_id: str
    idempotency_key: str
    status: ActionStatus
    duplicate: bool = False
    data: dict[str, Any] = Field(default_factory=dict)


class LookupCreditInput(StrictToolModel):
    account_id: str = Field(min_length=3, max_length=64)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
    external_reference: str | None = Field(default=None, min_length=3, max_length=64)

    @model_validator(mode="after")
    def require_lookup_key(self) -> "LookupCreditInput":
        if self.idempotency_key is None and self.external_reference is None:
            raise ValueError("Either idempotency_key or external_reference is required.")
        return self


class CreditLookupOutput(StrictToolModel):
    found: bool
    receipt: ActionReceiptOutput | None = None

    @model_validator(mode="after")
    def receipt_matches_found(self) -> "CreditLookupOutput":
        if self.found != (self.receipt is not None):
            raise ValueError("found must match receipt presence.")
        return self


class UpdateCaseStatusInput(StrictToolModel):
    case_id: str = Field(min_length=3, max_length=64)
    status: str = Field(min_length=3, max_length=32)
    idempotency_key: str = Field(min_length=8, max_length=128)
    scenario: ProviderScenario = ProviderScenario.SUCCESS


class EscalateInput(StrictToolModel):
    case_id: str = Field(min_length=3, max_length=64)
    reason: str = Field(min_length=8, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)
    scenario: ProviderScenario = ProviderScenario.SUCCESS


class NotifyTeamInput(StrictToolModel):
    case_id: str = Field(min_length=3, max_length=64)
    team: str = Field(min_length=2, max_length=64)
    message: str = Field(min_length=8, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)
    scenario: ProviderScenario = ProviderScenario.SUCCESS
