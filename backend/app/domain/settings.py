from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SettingsSection(StrEnum):
    GENERAL = "general"
    APPROVALS = "approvals"
    NOTIFICATIONS = "notifications"
    SECURITY = "security"
    RETENTION = "retention"


class GeneralSettingsValues(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_name: str = Field(min_length=1, max_length=200)
    locale: str = Field(pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$", max_length=16)
    time_zone: str = Field(min_length=1, max_length=100)

    @field_validator("time_zone")
    @classmethod
    def validate_time_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("time_zone must be a valid IANA time zone") from exc
        return value


class ApprovalSettingsValues(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    administrator_financial_limits: dict[str, Decimal] = Field(min_length=1, max_length=20)
    require_decision_reason: Literal[True] = True

    @field_validator("administrator_financial_limits")
    @classmethod
    def validate_financial_limits(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        normalized: dict[str, Decimal] = {}
        for currency, amount in value.items():
            code = currency.upper()
            if len(code) != 3 or not code.isalpha():
                raise ValueError("financial limit currencies must use three-letter codes")
            if amount <= 0 or amount > Decimal("9999999999999999.99"):
                raise ValueError("financial limits must be greater than zero")
            normalized[code] = amount.quantize(Decimal("0.01"))
        return dict(sorted(normalized.items()))


class NotificationSettingsValues(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sla_risk_alerts: bool = True
    review_waiting_alerts: bool = True
    action_recovery_alerts: bool = True
    email_delivery: bool = False


class SecuritySettingsValues(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hide_sensitive_customer_fields: bool = True
    session_duration_minutes: int = Field(default=480, ge=15, le=1440)


class RetentionSettingsValues(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_retention_days: int = Field(default=2555, ge=365, le=3650)
    conversation_retention_days: int = Field(default=730, ge=30, le=3650)
    legal_hold_enabled: bool = True

    @model_validator(mode="after")
    def audit_outlives_conversations(self) -> Self:
        if self.audit_retention_days < self.conversation_retention_days:
            raise ValueError(
                "audit retention cannot be shorter than conversation retention"
            )
        return self


type SettingsValues = (
    GeneralSettingsValues
    | ApprovalSettingsValues
    | NotificationSettingsValues
    | SecuritySettingsValues
    | RetentionSettingsValues
)


class OrganizationSettingsRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID | None
    public_id: str
    organization_id: UUID
    organization_public_id: str
    section: SettingsSection
    configuration: SettingsValues
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    persisted: bool


class SettingsUpdateReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    settings: OrganizationSettingsRecord
    changed_by_id: str
    changed_by_name: str
    changed_at: datetime
    correlation_id: str


DEFAULT_ADMINISTRATOR_FINANCIAL_LIMITS: dict[str, Decimal] = {
    "EUR": Decimal("1000.00"),
    "GBP": Decimal("1000.00"),
    "IDR": Decimal("15000000.00"),
    "SGD": Decimal("1500.00"),
    "USD": Decimal("1000.00"),
}


def default_settings(
    section: SettingsSection,
    *,
    organization_name: str,
) -> SettingsValues:
    if section is SettingsSection.GENERAL:
        return GeneralSettingsValues(
            organization_name=organization_name,
            locale="en-US",
            time_zone="Asia/Jakarta",
        )
    if section is SettingsSection.APPROVALS:
        return ApprovalSettingsValues(
            administrator_financial_limits=DEFAULT_ADMINISTRATOR_FINANCIAL_LIMITS,
        )
    if section is SettingsSection.NOTIFICATIONS:
        return NotificationSettingsValues()
    if section is SettingsSection.SECURITY:
        return SecuritySettingsValues()
    return RetentionSettingsValues()


def parse_settings_values(
    section: SettingsSection,
    value: object,
) -> SettingsValues:
    if section is SettingsSection.GENERAL:
        return GeneralSettingsValues.model_validate(value)
    if section is SettingsSection.APPROVALS:
        return ApprovalSettingsValues.model_validate(value)
    if section is SettingsSection.NOTIFICATIONS:
        return NotificationSettingsValues.model_validate(value)
    if section is SettingsSection.SECURITY:
        return SecuritySettingsValues.model_validate(value)
    return RetentionSettingsValues.model_validate(value)


class SettingsNotFound(LookupError):
    pass


class SettingsConflict(RuntimeError):
    pass


class SettingsVersionConflict(RuntimeError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            f"The settings changed after version {expected_version}; current version is "
            f"{current_version}."
        )
        self.expected_version = expected_version
        self.current_version = current_version
