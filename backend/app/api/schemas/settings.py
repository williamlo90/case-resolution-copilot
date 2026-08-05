from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from app.api.schemas.common import (
    ActorSummaryResponse,
    ApiSchema,
    DataResponse,
    PublicId,
    UtcDateTime,
    Version,
)
from app.domain.settings import (
    ApprovalSettingsValues,
    GeneralSettingsValues,
    NotificationSettingsValues,
    RetentionSettingsValues,
    SecuritySettingsValues,
)


class GeneralSettingsConfiguration(ApiSchema):
    organization_name: str = Field(min_length=1, max_length=200)
    locale: str = Field(pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$", max_length=16)
    time_zone: str = Field(min_length=1, max_length=100)


class ApprovalSettingsConfiguration(ApiSchema):
    administrator_financial_limits: dict[str, Decimal]
    require_decision_reason: Literal[True] = True


class NotificationSettingsConfiguration(ApiSchema):
    sla_risk_alerts: bool
    review_waiting_alerts: bool
    action_recovery_alerts: bool
    email_delivery: bool


class SecuritySettingsConfiguration(ApiSchema):
    hide_sensitive_customer_fields: bool
    session_duration_minutes: int = Field(ge=15, le=1440)


class RetentionSettingsConfiguration(ApiSchema):
    audit_retention_days: int = Field(ge=365, le=3650)
    conversation_retention_days: int = Field(ge=30, le=3650)
    legal_hold_enabled: bool


class SettingsBaseResponse(ApiSchema):
    id: PublicId
    organization_id: PublicId
    version: Version
    updated_at: UtcDateTime
    using_defaults: bool


class GeneralSettingsResponse(SettingsBaseResponse):
    section: Literal["general"]
    configuration: GeneralSettingsConfiguration


class ApprovalSettingsResponse(SettingsBaseResponse):
    section: Literal["approvals"]
    configuration: ApprovalSettingsConfiguration


class NotificationSettingsResponse(SettingsBaseResponse):
    section: Literal["notifications"]
    configuration: NotificationSettingsConfiguration


class SecuritySettingsResponse(SettingsBaseResponse):
    section: Literal["security"]
    configuration: SecuritySettingsConfiguration


class RetentionSettingsResponse(SettingsBaseResponse):
    section: Literal["retention"]
    configuration: RetentionSettingsConfiguration


SettingsResponse = Annotated[
    GeneralSettingsResponse
    | ApprovalSettingsResponse
    | NotificationSettingsResponse
    | SecuritySettingsResponse
    | RetentionSettingsResponse,
    Field(discriminator="section"),
]


class UpdateGeneralSettingsRequest(ApiSchema):
    section: Literal["general"]
    expected_version: Version
    configuration: GeneralSettingsValues


class UpdateApprovalSettingsRequest(ApiSchema):
    section: Literal["approvals"]
    expected_version: Version
    configuration: ApprovalSettingsValues


class UpdateNotificationSettingsRequest(ApiSchema):
    section: Literal["notifications"]
    expected_version: Version
    configuration: NotificationSettingsValues


class UpdateSecuritySettingsRequest(ApiSchema):
    section: Literal["security"]
    expected_version: Version
    configuration: SecuritySettingsValues


class UpdateRetentionSettingsRequest(ApiSchema):
    section: Literal["retention"]
    expected_version: Version
    configuration: RetentionSettingsValues


SettingsUpdateRequest = Annotated[
    UpdateGeneralSettingsRequest
    | UpdateApprovalSettingsRequest
    | UpdateNotificationSettingsRequest
    | UpdateSecuritySettingsRequest
    | UpdateRetentionSettingsRequest,
    Field(discriminator="section"),
]


class SettingsUpdateReceiptResponse(ApiSchema):
    settings: SettingsResponse
    changed_by: ActorSummaryResponse
    changed_at: UtcDateTime
    correlation_id: str = Field(min_length=1, max_length=128)


class SettingsDetailEnvelope(DataResponse[SettingsResponse]):
    pass


class SettingsUpdateEnvelope(DataResponse[SettingsUpdateReceiptResponse]):
    pass


def domain_settings_values(
    command: SettingsUpdateRequest,
) -> (
    GeneralSettingsValues
    | ApprovalSettingsValues
    | NotificationSettingsValues
    | SecuritySettingsValues
    | RetentionSettingsValues
):
    if command.section == "general":
        return command.configuration
    if command.section == "approvals":
        return command.configuration
    if command.section == "notifications":
        return command.configuration
    if command.section == "security":
        return command.configuration
    return command.configuration
