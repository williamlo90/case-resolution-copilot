from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import Table

from app.persistence.action_repository import _connection_is_eligible
from app.persistence.models import (
    CaseActionAttemptModel,
    CaseActionModel,
    CaseActionReceiptModel,
    CaseActionReconciliationModel,
    ConnectionHealthCheckModel,
    ConnectionModel,
)

NOW = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)


def test_action_and_connection_tables_are_tenant_scoped_and_generic() -> None:
    tables = [
        ConnectionModel.__table__,
        ConnectionHealthCheckModel.__table__,
        CaseActionModel.__table__,
        CaseActionAttemptModel.__table__,
        CaseActionReceiptModel.__table__,
        CaseActionReconciliationModel.__table__,
    ]

    for table in tables:
        assert "organization_id" in table.c
        assert {
            "booking_id",
            "passenger_id",
            "airline",
            "pnr",
        }.isdisjoint(table.c.keys())


def test_connection_storage_never_defines_secret_value_columns() -> None:
    columns = set(ConnectionModel.__table__.c.keys())

    assert {
        "adapter_key",
        "credential_status",
        "read_capabilities",
        "write_capabilities",
        "action_types",
    } <= columns
    assert {
        "api_key",
        "access_token",
        "refresh_token",
        "password",
        "client_secret",
        "credentials",
    }.isdisjoint(columns)


def test_action_binds_exact_approval_and_idempotency_lineage() -> None:
    columns = set(CaseActionModel.__table__.c.keys())

    assert {
        "proposal_version_id",
        "proposed_action_id",
        "review_id",
        "review_snapshot_id",
        "review_decision_id",
        "connection_id",
        "typed_parameters",
        "idempotency_key",
        "authorization_expires_at",
        "execution_eligible",
    } <= columns
    assert {
        "prompt",
        "raw_provider_payload",
        "chain_of_thought",
        "reasoning",
    }.isdisjoint(columns)


def test_only_one_running_attempt_and_reconciliation_can_exist() -> None:
    attempt_table = cast(Table, CaseActionAttemptModel.__table__)
    reconciliation_table = cast(
        Table,
        CaseActionReconciliationModel.__table__,
    )
    attempt_index = next(
        index for index in attempt_table.indexes if index.name == "uq_case_action_attempts_running"
    )
    reconciliation_index = next(
        index
        for index in reconciliation_table.indexes
        if index.name == "uq_case_action_reconciliations_running"
    )

    assert attempt_index.unique
    assert attempt_index.dialect_options["postgresql"]["where"] is not None
    assert reconciliation_index.unique
    assert reconciliation_index.dialect_options["postgresql"]["where"] is not None


def test_action_write_requires_a_recent_healthy_connection_check() -> None:
    connection = ConnectionModel(
        id=UUID(int=1),
        public_id="CN-TEST",
        organization_id=UUID(int=2),
        name="Billing demo",
        provider_type="billing",
        adapter_key="deterministic_demo",
        environment="demo",
        health="healthy",
        last_checked_at=NOW - timedelta(minutes=14),
        credential_status="demo",
        read_capabilities=[],
        write_capabilities=["issue_refund"],
        action_types=["issue_refund"],
        affected_work=[],
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )

    assert _connection_is_eligible(connection, now=NOW)
    connection.last_checked_at = NOW - timedelta(minutes=15)
    assert not _connection_is_eligible(connection, now=NOW)
    connection.last_checked_at = NOW
    connection.credential_status = "expired"
    assert not _connection_is_eligible(connection, now=NOW)
