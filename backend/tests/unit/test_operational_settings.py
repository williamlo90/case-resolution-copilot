from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.settings import (
    ApprovalSettingsValues,
    GeneralSettingsValues,
    RetentionSettingsValues,
    SettingsSection,
    default_settings,
    parse_settings_values,
)


def test_each_settings_section_has_typed_credential_free_defaults() -> None:
    defaults = {
        section: default_settings(
            section,
            organization_name="Northstar Cloud",
        )
        for section in SettingsSection
    }

    assert isinstance(defaults[SettingsSection.GENERAL], GeneralSettingsValues)
    assert isinstance(defaults[SettingsSection.APPROVALS], ApprovalSettingsValues)
    approval = defaults[SettingsSection.APPROVALS]
    assert isinstance(approval, ApprovalSettingsValues)
    assert approval.administrator_financial_limits["IDR"] == Decimal("15000000.00")
    assert approval.require_decision_reason is True
    assert "secret" not in " ".join(
        key
        for value in defaults.values()
        for key in value.model_dump(mode="json")
    )


def test_approval_settings_normalize_currency_and_reject_unsafe_reason_rule() -> None:
    values = ApprovalSettingsValues(
        administrator_financial_limits={"usd": Decimal("250.129")},
    )

    assert values.administrator_financial_limits == {"USD": Decimal("250.13")}
    with pytest.raises(ValidationError):
        ApprovalSettingsValues(
            administrator_financial_limits={"USD": Decimal("250.00")},
            require_decision_reason=False,
        )


def test_section_parser_rejects_fields_from_another_section() -> None:
    with pytest.raises(ValidationError):
        parse_settings_values(
            SettingsSection.SECURITY,
            {
                "organization_name": "Northstar Cloud",
                "locale": "en-US",
                "time_zone": "Asia/Jakarta",
            },
        )


def test_general_settings_reject_unknown_time_zone() -> None:
    with pytest.raises(ValidationError, match="valid IANA time zone"):
        GeneralSettingsValues(
            organization_name="Northstar Cloud",
            locale="en-US",
            time_zone="Somewhere/Unknown",
        )


def test_audit_retention_cannot_end_before_conversation_retention() -> None:
    with pytest.raises(ValidationError, match="cannot be shorter"):
        RetentionSettingsValues(
            audit_retention_days=365,
            conversation_retention_days=730,
        )
