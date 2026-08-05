from typing import cast

from sqlalchemy import Index, Table

from app.persistence.models import (
    CaseReviewDecisionModel,
    CaseReviewModel,
    CaseReviewReservationModel,
    CaseReviewSnapshotModel,
)


def test_review_tables_are_generic_and_tenant_scoped() -> None:
    tables = [
        CaseReviewModel.__table__,
        CaseReviewSnapshotModel.__table__,
        CaseReviewReservationModel.__table__,
        CaseReviewDecisionModel.__table__,
    ]

    for table in tables:
        columns = set(table.c.keys())
        assert {"organization_id", "case_id", "review_id"} - columns <= {"review_id"}
        assert {"booking_id", "passenger_id", "airline"}.isdisjoint(columns)


def test_review_snapshot_binds_complete_authorization_context() -> None:
    columns = set(CaseReviewSnapshotModel.__table__.c.keys())

    assert {
        "case_version",
        "proposal_version",
        "proposal_fingerprint",
        "context_fingerprint",
        "evidence_fingerprint",
        "risk_fingerprint",
        "risk_rule_version",
        "snapshot_fingerprint",
        "approval_rule_id",
        "approval_rule_version",
        "required_role",
        "execution_eligible",
    } <= columns
    assert {
        "prompt",
        "raw_payload",
        "reasoning",
        "chain_of_thought",
    }.isdisjoint(columns)


def test_review_has_one_active_reservation_and_immutable_legacy_lineage() -> None:
    table = cast(Table, CaseReviewReservationModel.__table__)
    indexes: set[Index] = table.indexes
    active = next(index for index in indexes if index.name == "uq_case_review_reservations_active")

    assert active.unique
    assert active.dialect_options["postgresql"]["where"] is not None
    assert "legacy_reservation_id" in CaseReviewReservationModel.__table__.c
    assert "legacy_decision_id" in CaseReviewDecisionModel.__table__.c
    assert CaseReviewReservationModel.__table__.c.reviewer_id.nullable
    assert CaseReviewDecisionModel.__table__.c.reviewer_id.nullable
