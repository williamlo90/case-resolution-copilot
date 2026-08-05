from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.api.schemas.actions import ActionDetailResponse, ActionSummaryResponse
from app.api.schemas.audit import AuditEventResponse
from app.api.schemas.cases import (
    BusinessObjectSnapshotResponse,
    CaseListResponse,
    CaseQueueSummaryResponse,
    CaseSummaryResponse,
    CaseWorkspaceResponse,
)
from app.api.schemas.common import MoneyResponse, SourceFreshnessResponse
from app.api.schemas.connections import ConnectionResponse
from app.api.schemas.conversations import ConversationThreadResponse
from app.api.schemas.organizations import MemberResponse, OrganizationResponse
from app.api.schemas.policies import PolicyDetailResponse, PolicySummaryResponse
from app.api.schemas.proposals import ProposalResponse
from app.api.schemas.reviews import ReviewSnapshotResponse, ReviewSummaryResponse


def _property_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        property_names = set(value.get("properties", {}).keys())
        for nested in value.values():
            property_names.update(_property_names(nested))
        return property_names
    if isinstance(value, list):
        list_names: set[str] = set()
        for nested in value:
            list_names.update(_property_names(nested))
        return list_names
    return set()


@pytest.mark.parametrize(
    "model",
    [
        OrganizationResponse,
        MemberResponse,
        CaseWorkspaceResponse,
        ConversationThreadResponse,
        PolicyDetailResponse,
        ProposalResponse,
        ReviewSnapshotResponse,
        ActionDetailResponse,
        ConnectionResponse,
        AuditEventResponse,
    ],
)
def test_generic_contracts_do_not_require_travel_fields(model: type[BaseModel]) -> None:
    property_names = _property_names(model.model_json_schema())

    assert property_names.isdisjoint({"booking", "passenger", "itinerary", "airline"})


def test_primary_read_contracts_cover_frontend_adapter_fields() -> None:
    assert {
        "id",
        "source_id",
        "external_reference",
        "category",
        "issue",
        "customer",
        "status",
        "owner",
        "urgency",
        "risk",
        "sla_minutes_remaining",
        "updated_at",
        "source_freshness",
        "impact",
    } <= CaseSummaryResponse.model_fields.keys()
    assert {
        "id",
        "case_id",
        "proposal",
        "impact",
        "review_reason",
        "policy_state",
        "uncertainty",
        "snapshot_freshness",
        "status",
        "reservation",
    } <= ReviewSummaryResponse.model_fields.keys()
    assert {
        "id",
        "case_id",
        "type",
        "label",
        "target",
        "impact",
        "status",
        "attempt_count",
        "owner",
        "updated_at",
        "recovery_required",
    } <= ActionSummaryResponse.model_fields.keys()
    assert {
        "id",
        "title",
        "description",
        "status",
        "owner",
        "applies_to",
        "current_version",
        "source",
        "health",
        "used_by_cases",
        "updated_at",
    } <= PolicySummaryResponse.model_fields.keys()


def test_mutable_resources_expose_optimistic_version() -> None:
    resources: list[type[BaseModel]] = [
        OrganizationResponse,
        MemberResponse,
        CaseSummaryResponse,
        BusinessObjectSnapshotResponse,
        ConversationThreadResponse,
        PolicySummaryResponse,
        ProposalResponse,
        ReviewSummaryResponse,
        ActionSummaryResponse,
        ConnectionResponse,
    ]

    assert all("version" in resource.model_fields for resource in resources)


def test_money_serializes_as_exact_decimal_string() -> None:
    payload = MoneyResponse(amount=Decimal("125.50"), currency="USD").model_dump(mode="json")

    assert payload == {"amount": "125.50", "currency": "USD"}


def test_contract_rejects_non_utc_timestamps_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SourceFreshnessResponse(
            status="current",
            checked_at=datetime(2026, 7, 22, tzinfo=timezone(timedelta(hours=7))),
        )
    with pytest.raises(ValidationError):
        MoneyResponse.model_validate(
            {"amount": Decimal("1.00"), "currency": "USD", "secret": "not-allowed"}
        )


def test_list_envelope_has_stable_contract_metadata() -> None:
    response = CaseListResponse(
        items=[],
        next_cursor=None,
        previous_cursor=None,
        total=0,
        offset=0,
        limit=8,
        summary_scope="organization",
        summary=CaseQueueSummaryResponse(
            total=0,
            attention=0,
            review=0,
            sla_at_risk=0,
            unassigned=0,
        ),
    )

    assert response.meta.data_mode == "demo"
    assert response.meta.contract_version == "2026-07-22"
