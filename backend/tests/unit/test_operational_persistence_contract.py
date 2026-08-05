from typing import cast

from sqlalchemy import Table, UniqueConstraint

from app.persistence.models import (
    CaseDataGovernanceModel,
    CaseQualityProjectionModel,
    NotificationModel,
    NotificationOutboxModel,
    OrganizationSettingModel,
)


def _unique_names(table: Table) -> set[str | None]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and isinstance(constraint.name, str)
    }


def test_operational_control_tables_are_tenant_scoped_and_generic() -> None:
    tables = [
        OrganizationSettingModel.__table__,
        NotificationModel.__table__,
        NotificationOutboxModel.__table__,
        CaseDataGovernanceModel.__table__,
        CaseQualityProjectionModel.__table__,
    ]

    for model_table in tables:
        table = cast(Table, model_table)
        assert "organization_id" in table.c
        assert {"booking_id", "passenger_id", "airline", "pnr"}.isdisjoint(
            table.c.keys()
        )


def test_settings_notifications_and_quality_have_idempotent_tenant_keys() -> None:
    settings = cast(Table, OrganizationSettingModel.__table__)
    notifications = cast(Table, NotificationModel.__table__)
    quality = cast(Table, CaseQualityProjectionModel.__table__)

    assert "uq_organization_settings_org_section" in _unique_names(settings)
    assert "uq_notifications_org_recipient_event" in _unique_names(notifications)
    assert "uq_case_quality_projections_org_case_category" in _unique_names(quality)


def test_notification_outbox_stores_no_raw_destination_or_credentials() -> None:
    columns = set(NotificationOutboxModel.__table__.c.keys())

    assert {"destination_fingerprint", "payload", "status", "attempt_count"} <= columns
    assert {
        "email",
        "phone",
        "address",
        "api_key",
        "access_token",
        "password",
        "secret",
    }.isdisjoint(columns)


def test_retention_table_records_state_without_destructive_commands() -> None:
    columns = set(CaseDataGovernanceModel.__table__.c.keys())

    assert {
        "conversation_retention_until",
        "audit_retention_until",
        "redaction_status",
        "legal_hold",
        "source_fingerprint",
    } <= columns
    assert {"delete_at", "purge_command", "raw_customer_data"}.isdisjoint(columns)
