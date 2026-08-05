from typing import cast

from sqlalchemy import ForeignKeyConstraint, Table, UniqueConstraint

from app.persistence.models import (
    BusinessObjectSnapshotModel,
    CaseModel,
    CaseRequestModel,
    ConversationMessageModel,
    ConversationThreadModel,
    ResponseDraftModel,
)


def _unique_constraint_names(table: Table) -> set[str | None]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and isinstance(constraint.name, str)
    }


def _scoped_foreign_key_names(table: Table) -> set[str | None]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and len(constraint.columns) >= 2
        and isinstance(constraint.name, str)
    }


def _foreign_key_columns(table: Table, name: str) -> tuple[str, ...]:
    constraint = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint) and constraint.name == name
    )
    return tuple(column.name for column in constraint.columns)


def test_generic_case_roots_define_tenant_scoped_identity() -> None:
    assert {
        "uq_cases_org_id",
        "uq_cases_org_public",
        "uq_cases_org_source",
        "uq_cases_legacy_task",
    } <= _unique_constraint_names(cast(Table, CaseModel.__table__))
    assert "uq_conversation_threads_org_case" in _unique_constraint_names(
        cast(Table, ConversationThreadModel.__table__)
    )


def test_case_children_use_composite_tenant_foreign_keys() -> None:
    assert "fk_case_requests_org_case" in _scoped_foreign_key_names(
        cast(Table, CaseRequestModel.__table__)
    )
    assert "fk_business_snapshots_org_case" in _scoped_foreign_key_names(
        cast(Table, BusinessObjectSnapshotModel.__table__)
    )
    assert {
        "fk_conversation_messages_org_case",
        "fk_conversation_messages_org_thread",
    } <= _scoped_foreign_key_names(cast(Table, ConversationMessageModel.__table__))
    assert _foreign_key_columns(
        cast(Table, ConversationMessageModel.__table__),
        "fk_conversation_messages_org_thread",
    ) == ("organization_id", "case_id", "thread_id")
    assert "fk_response_drafts_org_case" in _scoped_foreign_key_names(
        cast(Table, ResponseDraftModel.__table__)
    )


def test_generic_case_tables_do_not_embed_travel_columns() -> None:
    generic_columns = {
        column.name
        for model in (
            CaseModel,
            CaseRequestModel,
            BusinessObjectSnapshotModel,
            ConversationThreadModel,
            ConversationMessageModel,
            ResponseDraftModel,
        )
        for column in model.__table__.columns
    }

    assert {"booking_reference", "flight_number", "passenger_count"}.isdisjoint(generic_columns)
