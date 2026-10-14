from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain.controlled_operations import OPERATIONS
from app.integrations.action_gateway import DeterministicActionGateway, GatewayBehavior
from app.persistence.database import Database
from app.persistence.models import BusinessObjectSnapshotModel, CaseModel
from tests.integration.test_case_action_api import _app, _seed_connections
from tests.integration.test_case_review_api import ADMIN, SUPERVISOR, _seed_workspace
from tests.unit.test_controlled_operations import operation_workspace


def publish_operation(client: TestClient, action: str, source: str) -> None:
    spec = OPERATIONS[action]
    created = client.post(
        "/api/policies",
        headers=ADMIN,
        json={
            "public_id": "POL-CONTROLLED",
            "title": "Controlled business operation",
            "description": "Synthetic reviewed operation with explicit target parameters.",
            "source": {"kind": "manual", "name": "Controlled operation test"},
            "source_text": source,
            "applicability": {
                "decision_scope": "controlled_business_operation",
                "case_categories": [spec.category],
                "products": ["all"],
                "regions": ["all"],
                "channels": ["all"],
                "customer_tiers": ["all"],
            },
            "effective_from": "2026-01-01T00:00:00Z",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    for endpoint in ("submit-review", "publish"):
        version = body["versions"][0]
        command: dict[str, Any] = dict(
            expected_policy_version=body["policy"]["version"],
            expected_version=version["record_version"],
        )
        if endpoint == "publish":
            command["effective_from"] = "2026-01-01T00:00:00Z"
        result = client.post(
            f"/api/policies/POL-CONTROLLED/versions/1/{endpoint}", headers=ADMIN, json=command
        )
        assert result.status_code == 200, result.text
        body = result.json()["data"]


@pytest.mark.parametrize("operation", ["rename_account", "change_draft_currency"])
def test_new_operation_uses_published_sop_approval_and_observable_target(
    database: Database,
    test_database_url: str,
    operation: str,
) -> None:
    workspace, evidence = operation_workspace(operation)
    _seed_workspace(database)
    _seed_connections(database)
    with database.session() as session:
        case = session.scalar(select(CaseModel).where(CaseModel.public_id == "CS-2047"))
        assert case is not None
        case.category = workspace.case.category.value
        case.impact_amount = workspace.case.impact_amount
        case.impact_currency = workspace.case.impact_currency
        rows = list(
            session.scalars(
                select(BusinessObjectSnapshotModel).where(
                    BusinessObjectSnapshotModel.case_id == case.id
                )
            )
        )
        assert rows
        for row in rows:
            row.fields = workspace.business_contexts[0].fields
            row.source_freshness = "current"
    app = _app(test_database_url)
    gateway = DeterministicActionGateway(
        objects={
            "SYNTHETIC-OBJECT-1": {
                "owner": "SYNTHETIC-OWNER-1",
                "invoice_state": "draft",
                "currency": "EUR",
                "new_name": "before",
            }
        },
        behaviors={operation: GatewayBehavior.OUTCOME_UNKNOWN_ACCEPTED},
    )
    app.state.action_gateway = gateway
    with TestClient(app) as client:
        connection = "CN-0002" if OPERATIONS[operation].scope else "CN-0001"
        assert (
            client.post(
                f"/api/connections/{connection}/test", headers=ADMIN, json={"expected_version": 1}
            ).status_code
            == 200
        )
        publish_operation(client, operation, evidence.evidence[0].version.source_text)
        generated = client.post(
            "/api/cases/CS-2047/proposals", headers=SUPERVISOR, json={"expected_case_version": 1}
        )
        assert generated.status_code == 201, generated.text
        assert generated.json()["data"]["proposal"]["state"] == "ready_for_review", generated.text
        review_result = client.post(
            "/api/cases/CS-2047/proposals/1/reviews",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        assert review_result.status_code == 201, review_result.text
        review = review_result.json()["data"]["review"]
        reserved = client.post(
            f"/api/reviews/{review['id']}/reserve", headers=ADMIN, json={"expected_version": 1}
        )
        assert reserved.status_code == 200, reserved.text
        approved = client.post(
            f"/api/reviews/{review['id']}/decisions",
            headers=ADMIN,
            json={
                "expected_version": 2,
                "snapshot_fingerprint": review["snapshot_fingerprint"],
                "decision": "approve",
                "reason": "Checked exact target, owner, parameters and SOP.",
            },
        )
        assert approved.status_code == 200, approved.text
        actions = client.get("/api/actions", headers=SUPERVISOR).json()["items"]
        assert len(actions) == 1
        action_id = actions[0]["id"]
        executed = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        )
        assert executed.status_code == 200, executed.text
        action = executed.json()["data"]["action"]
        assert action["type"] == operation and action["status"] == "outcome_unknown"
        assert action["target"] == "SYNTHETIC-OBJECT-1"
        assert (
            client.post(
                f"/api/actions/{action_id}/execute",
                headers=SUPERVISOR,
                json={"expected_version": action["version"]},
            ).status_code
            == 409
        )
        verified = client.post(
            f"/api/actions/{action_id}/reconcile",
            headers=SUPERVISOR,
            json={"expected_version": action["version"]},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["data"]["action"]["status"] == "completed"
        target = gateway.controlled_target.objects["SYNTHETIC-OBJECT-1"]
        assert target["owner"] == "SYNTHETIC-OWNER-1"
        assert target["new_name" if operation == "rename_account" else "currency"] == (
            "synthetic-new-value" if operation == "rename_account" else "USD"
        )
        assert len(gateway.controlled_target.effects) == 1
