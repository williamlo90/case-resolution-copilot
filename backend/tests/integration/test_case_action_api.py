from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.integrations.action_gateway import (
    DeterministicActionGateway,
    GatewayBehavior,
)
from app.integrations.connection_seed import deterministic_connection_seeds
from app.main import create_app
from app.persistence.connection_repository import ConnectionRepository
from app.persistence.database import Database
from app.persistence.models import (
    CaseActionAttemptModel,
    CaseActionModel,
    CaseActionReceiptModel,
)
from app.security.authentication import (
    DETERMINISTIC_ACTORS,
    DeterministicAuthProvider,
)
from tests.integration.test_case_review_api import (
    ADMIN,
    OTHER_ADMIN,
    SPECIALIST,
    SUPERVISOR,
    _other_actor,
    _publish_refund_policy,
    _seed_workspace,
)


def _app(database_url: str) -> FastAPI:
    app = create_app(
        Settings(
            environment="test",
            database_url=database_url,
            _env_file=None,
        )
    )
    app.state.auth_provider = DeterministicAuthProvider(
        {**DETERMINISTIC_ACTORS, "USR-9001": _other_actor()}
    )
    return app


def _seed_connections(database: Database) -> None:
    with database.session() as session:
        repository = ConnectionRepository(session)
        for command in deterministic_connection_seeds():
            repository.seed(
                organization_public_id="ORG-0001",
                command=command,
                correlation_id=f"action-test-seed:{command.public_id}",
            )


def _approve_refund_action(client: TestClient) -> str:
    _publish_refund_policy(client)
    generated = client.post(
        "/api/cases/CS-2047/proposals",
        headers=SUPERVISOR,
        json={"expected_case_version": 1},
    )
    assert generated.status_code == 201
    submitted = client.post(
        "/api/cases/CS-2047/proposals/1/reviews",
        headers=SUPERVISOR,
        json={"expected_case_version": 1},
    )
    assert submitted.status_code == 201
    review = submitted.json()["data"]["review"]
    review_id = review["id"]
    reserved = client.post(
        f"/api/reviews/{review_id}/reserve",
        headers=ADMIN,
        json={"expected_version": 1},
    )
    assert reserved.status_code == 200
    approved = client.post(
        f"/api/reviews/{review_id}/decisions",
        headers=ADMIN,
        json={
            "expected_version": 2,
            "snapshot_fingerprint": review["snapshot_fingerprint"],
            "decision": "approve",
            "reason": "Evidence, impact, target, and policy authority were verified.",
        },
    )
    assert approved.status_code == 200
    queue = client.get("/api/actions", headers=SUPERVISOR)
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    action_id = queue.json()["items"][0]["id"]
    assert isinstance(action_id, str)
    return action_id


def test_approved_action_executes_once_with_durable_receipt(
    database: Database,
    test_database_url: str,
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    app = _app(test_database_url)

    with TestClient(app) as client:
        connections = client.get("/api/connections", headers=ADMIN)
        tested_connection = client.post(
            "/api/connections/CN-0001/test",
            headers=ADMIN,
            json={"expected_version": 1},
        )
        action_id = _approve_refund_action(client)
        specialist_detail = client.get(
            f"/api/actions/{action_id}",
            headers=SPECIALIST,
        )
        supervisor_detail = client.get(
            f"/api/actions/{action_id}",
            headers=SUPERVISOR,
        )
        hidden = client.get(
            f"/api/actions/{action_id}",
            headers=OTHER_ADMIN,
        )
        executed = client.post(
            f"/api/actions/{action_id}/execute",
            headers=SUPERVISOR,
            json={"expected_version": 1},
        )
        duplicate = client.post(
            f"/api/actions/{action_id}/execute",
            headers=SUPERVISOR,
            json={"expected_version": executed.json()["data"]["action"]["version"]},
        )

    assert connections.status_code == 200
    assert connections.json()["total"] == 3
    assert "adapter_key" not in connections.json()["items"][0]
    assert "credentials" not in connections.json()["items"][0]
    assert tested_connection.status_code == 200
    assert tested_connection.json()["data"]["connection"]["health"] == "healthy"
    assert tested_connection.json()["data"]["connection"]["version"] == 2
    assert tested_connection.json()["data"]["receipt"]["detail"]
    assert specialist_detail.status_code == 200
    assert specialist_detail.json()["data"]["execution_blocker"] == "permission"
    assert "execute" not in specialist_detail.json()["data"]["available_commands"]
    assert supervisor_detail.status_code == 200
    assert supervisor_detail.json()["data"]["execution_blocker"] is None
    assert supervisor_detail.json()["data"]["available_commands"] == ["execute"]
    assert hidden.status_code == 404
    assert executed.status_code == 200
    executed_detail = executed.json()["data"]
    assert executed_detail["action"]["status"] == "completed"
    assert executed_detail["action"]["attempt_count"] == 1
    assert executed_detail["receipt"]["external_reference"]
    assert executed_detail["attempts"][0]["outcome"] == "succeeded"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["details"]["blocker"] == "duplicate"

    with database.session() as session:
        assert session.scalar(select(func.count(CaseActionModel.id))) == 1
        assert session.scalar(select(func.count(CaseActionAttemptModel.id))) == 1
        assert session.scalar(select(func.count(CaseActionReceiptModel.id))) == 1


def test_unknown_outcome_blocks_retry_until_read_only_reconciliation(
    database: Database,
    test_database_url: str,
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    app = _app(test_database_url)
    app.state.action_gateway = DeterministicActionGateway(
        behaviors={
            "issue_refund": GatewayBehavior.OUTCOME_UNKNOWN_ACCEPTED,
        }
    )

    with TestClient(app) as client:
        action_id = _approve_refund_action(client)
        executed = client.post(
            f"/api/actions/{action_id}/execute",
            headers=SUPERVISOR,
            json={"expected_version": 1},
        )
        unknown = executed.json()["data"]
        reconciled = client.post(
            f"/api/actions/{action_id}/reconcile",
            headers=SUPERVISOR,
            json={"expected_version": unknown["action"]["version"]},
        )

    assert executed.status_code == 200
    assert unknown["action"]["status"] == "outcome_unknown"
    assert "retry_safe" not in unknown["available_commands"]
    assert "reconcile" in unknown["available_commands"]
    assert unknown["receipt"] is None
    assert reconciled.status_code == 200
    reconciled_detail = reconciled.json()["data"]
    assert reconciled_detail["action"]["status"] == "completed"
    assert reconciled_detail["receipt"]["external_reference"]
    assert reconciled_detail["reconciliations"][-1]["outcome"] == "confirmed_completed"
