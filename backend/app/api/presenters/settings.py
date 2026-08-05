from app.api.schemas.common import ActorSummaryResponse
from app.api.schemas.settings import (
    ApprovalSettingsConfiguration,
    ApprovalSettingsResponse,
    GeneralSettingsConfiguration,
    GeneralSettingsResponse,
    NotificationSettingsConfiguration,
    NotificationSettingsResponse,
    RetentionSettingsConfiguration,
    RetentionSettingsResponse,
    SecuritySettingsConfiguration,
    SecuritySettingsResponse,
    SettingsResponse,
    SettingsUpdateReceiptResponse,
)
from app.domain.settings import (
    ApprovalSettingsValues,
    GeneralSettingsValues,
    NotificationSettingsValues,
    OrganizationSettingsRecord,
    RetentionSettingsValues,
    SecuritySettingsValues,
    SettingsUpdateReceipt,
)


def present_settings(record: OrganizationSettingsRecord) -> SettingsResponse:
    values = record.configuration
    if isinstance(values, GeneralSettingsValues):
        return GeneralSettingsResponse(
            id=record.public_id,
            organization_id=record.organization_public_id,
            version=record.version,
            updated_at=record.updated_at,
            using_defaults=not record.persisted,
            section="general",
            configuration=GeneralSettingsConfiguration.model_validate(values.model_dump()),
        )
    if isinstance(values, ApprovalSettingsValues):
        return ApprovalSettingsResponse(
            id=record.public_id,
            organization_id=record.organization_public_id,
            version=record.version,
            updated_at=record.updated_at,
            using_defaults=not record.persisted,
            section="approvals",
            configuration=ApprovalSettingsConfiguration.model_validate(values.model_dump()),
        )
    if isinstance(values, NotificationSettingsValues):
        return NotificationSettingsResponse(
            id=record.public_id,
            organization_id=record.organization_public_id,
            version=record.version,
            updated_at=record.updated_at,
            using_defaults=not record.persisted,
            section="notifications",
            configuration=NotificationSettingsConfiguration.model_validate(values.model_dump()),
        )
    if isinstance(values, SecuritySettingsValues):
        return SecuritySettingsResponse(
            id=record.public_id,
            organization_id=record.organization_public_id,
            version=record.version,
            updated_at=record.updated_at,
            using_defaults=not record.persisted,
            section="security",
            configuration=SecuritySettingsConfiguration.model_validate(values.model_dump()),
        )
    if not isinstance(values, RetentionSettingsValues):
        raise TypeError("Unsupported settings configuration.")
    return RetentionSettingsResponse(
        id=record.public_id,
        organization_id=record.organization_public_id,
        version=record.version,
        updated_at=record.updated_at,
        using_defaults=not record.persisted,
        section="retention",
        configuration=RetentionSettingsConfiguration.model_validate(values.model_dump()),
    )


def present_settings_receipt(
    receipt: SettingsUpdateReceipt,
) -> SettingsUpdateReceiptResponse:
    return SettingsUpdateReceiptResponse(
        settings=present_settings(receipt.settings),
        changed_by=ActorSummaryResponse(
            id=receipt.changed_by_id,
            name=receipt.changed_by_name,
        ),
        changed_at=receipt.changed_at,
        correlation_id=receipt.correlation_id,
    )
