"""V1 workflows on the retained schema, without reviving retired operations."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.persistence.database import Database
from app.persistence.models import (
    CaseActionAttemptModel,
    CaseActionModel,
    CaseModel,
    CaseResolutionEventModel,
)
from tests.integration.test_case_action_api import (
    _app,
    _approve_refund_action,
    _seed_connections,
)
from tests.integration.test_case_review_api import ADMIN, SUPERVISOR, _seed_workspace


def test_normal_workflow_preserves_historical_events(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    event_id = uuid4()
    with database.session() as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "20261013_0025"
        case = session.scalar(select(CaseModel).where(CaseModel.public_id == "CS-2047"))
        assert case is not None
        session.add(
            CaseResolutionEventModel(
                id=event_id,
                organization_id=case.organization_id,
                case_id=case.id,
                command_id="retained-history-fixture",
                kind="reopened",
                actor_id="USR-0003",
                correlation_id="retained-history-fixture",
                data={"reason": "Existing historical record"},
            )
        )
    with TestClient(_app(test_database_url)) as client:
        assert (
            client.post(
                "/api/connections/CN-0001/test", headers=ADMIN, json={"expected_version": 1}
            ).status_code
            == 200
        )
        action_id = _approve_refund_action(client)
        result = client.post(
            f"/api/actions/{action_id}/execute",
            headers=SUPERVISOR,
            json={"expected_version": 1},
        )
        assert result.status_code == 200
        assert result.json()["data"]["action"]["status"] == "completed"
        assert result.json()["data"]["receipt"]["external_reference"]
        assert client.get("/api/demo/v2/sessions", headers=ADMIN).status_code == 404
        assert client.get("/api/cases/CS-2047/resolution", headers=ADMIN).status_code == 404
        assert client.post("/api/demo/v2/sessions", headers=ADMIN, json={}).status_code == 404
        assert (
            client.post("/api/cases/CS-2047/resolution", headers=ADMIN, json={}).status_code == 404
        )
    with database.session() as session:
        historical = session.get(CaseResolutionEventModel, event_id)
        assert historical is not None
        assert historical.data == {"reason": "Existing historical record"}
        assert session.scalar(select(func.count(CaseResolutionEventModel.id))) == 1


@pytest.mark.parametrize("status", ["ready", "outcome_unknown"])
def test_retired_stored_action_is_readable_but_cannot_be_changed(
    database: Database, test_database_url: str, status: str
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    with TestClient(_app(test_database_url)) as client:
        action_id = _approve_refund_action(client)
        with database.session() as session:
            action = session.scalar(
                select(CaseActionModel).where(CaseActionModel.public_id == action_id)
            )
            assert action is not None
            action.type = "refund_course_fee"
            action.status = status
        detail = client.get(f"/api/actions/{action_id}", headers=ADMIN)
        assert detail.status_code == 200
        assert detail.json()["data"]["available_commands"] == []
        for command in ["execute", "retry", "reconcile", "manual-outcome", "escalate"]:
            payload: dict[str, object] = {"expected_version": 1}
            if command == "manual-outcome":
                payload.update(outcome="completed", reason="Cannot complete a retired operation")
            if command == "escalate":
                payload["reason"] = "Cannot mutate a retired operation"
            response = client.post(
                f"/api/actions/{action_id}/{command}", headers=ADMIN, json=payload
            )
            assert response.status_code == 409, (command, response.status_code)
        with database.session() as session:
            action = session.scalar(
                select(CaseActionModel).where(CaseActionModel.public_id == action_id)
            )
            assert action is not None
            assert action.status == status
            assert action.version == 1
            assert session.scalar(select(func.count(CaseActionAttemptModel.id))) == 0
