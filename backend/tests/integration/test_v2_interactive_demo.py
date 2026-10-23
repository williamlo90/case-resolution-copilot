"""Disposable PostgreSQL only: real commands through the synthetic browser adapter."""

from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.integrations.action_gateway import ActionGatewayRequest
from app.persistence.database import Database
from app.persistence.models import AuditEventModel, CaseModel, OrganizationModel
from tests.integration.test_case_action_api import _app
from tests.integration.test_case_review_api import ADMIN, OTHER_ADMIN, SPECIALIST, _seed_workspace


def create(client: TestClient, scenario: str = "verified_reopen") -> dict[str, Any]:
    response = client.post(
        "/api/demo/v2/sessions",
        headers=ADMIN,
        json={"scenario": scenario, "command_id": uuid4().hex},
    )
    assert response.status_code == 201, response.text
    view = response.json()["data"]
    assert view["workspace"]["case"]["id"] == view["case"]["id"]
    assert not view["lifecycle"]["closure"]["eligible"]
    assert "completed" not in view["lifecycle"]["available_commands"]
    return dict(response.json()["data"])


def command(
    client: TestClient,
    view: dict[str, Any],
    name: str,
    *,
    role: str = "specialist",
    reference: str | None = None,
    status: int = 200,
) -> dict[str, Any]:
    version = view["case"]["version"]
    if name in {"reserve", "approve"}:
        version = view["review"]["review"]["version"]
    if name in {"execute", "reconcile"}:
        version = view["action"]["action"]["version"]
    if name in {"publish_revision", "rollback"}:
        version = view["policy"]["policy"]["version"]
    body = {
        "command": name,
        "role": role,
        "expected_version": version,
        "command_id": uuid4().hex,
        "reason": "Operator verified this synthetic step.",
        "reference": reference,
        "expected_proposal_version": view["brief"]["proposal"]["version"]
        if view["brief"]
        else None,
        "resource_id": (view["review"]["review"]["id"] if view["review"] else None)
        if name in {"reserve", "approve"}
        else (view["action"]["action"]["id"] if view["action"] else None),
        "snapshot_fingerprint": view["review"]["review"]["snapshot_fingerprint"]
        if view["review"]
        else None,
    }
    path = f"/api/demo/v2/sessions/{view['session']['session_id']}"
    response = client.post(f"{path}/commands", headers=ADMIN, json=body)
    assert response.status_code == status, response.text
    if status == 200:
        return dict(response.json()["data"])
    refreshed = client.get(path, headers=ADMIN)
    assert refreshed.status_code == 200, refreshed.text
    return dict(refreshed.json()["data"])


def approve(client: TestClient, view: dict[str, Any]) -> dict[str, Any]:
    view = command(client, view, "generate")
    assert view["brief"]["proposal"]["state"] == "ready_for_review", view["brief"]
    view = command(client, view, "submit")
    view = command(client, view, "reserve", role="reviewer")
    return command(client, view, "approve", role="reviewer")


def test_demo_is_owner_scoped_and_cannot_write_existing_workspace(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    with TestClient(_app(test_database_url)) as client:
        forbidden = client.post(
            "/api/demo/v2/sessions",
            headers=SPECIALIST,
            json={"scenario": "verified_reopen", "command_id": uuid4().hex},
        )
        assert forbidden.status_code == 403
        view = create(client)
        path = f"/api/demo/v2/sessions/{view['session']['session_id']}"
        assert client.get(path, headers=OTHER_ADMIN).status_code == 404
        assert client.get(path).status_code == 401
        attack = client.post(
            f"{path}/commands",
            headers=ADMIN,
            json={
                "command": "generate",
                "role": "specialist",
                "expected_version": 1,
                "command_id": uuid4().hex,
                "reason": "Try cross-tenant case.",
                "case_id": "CS-2047",
            },
        )
        assert attack.status_code == 422
        assert client.get("/api/demo/v2/sessions", headers=OTHER_ADMIN).json()["items"] == []
        original = client.get("/api/cases/CS-2047", headers=ADMIN)
        assert original.status_code == 200
    with database.session() as session:
        root_cases = list(
            session.scalars(select(CaseModel).where(CaseModel.public_id == "CS-2047"))
        )
        assert len(root_cases) == 1 and root_cases[0].version == 1


def test_unmigrated_lifecycle_fails_before_creating_demo_data(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    # Reproduce an older deployed database without dropping or fabricating evidence.
    with database.session() as session:
        session.execute(
            text("ALTER TABLE case_resolution_events RENAME TO case_resolution_events_not_migrated")
        )
    try:
        with TestClient(_app(test_database_url)) as client:
            response = client.post(
                "/api/demo/v2/sessions",
                headers=ADMIN,
                json={"scenario": "verified_reopen", "command_id": uuid4().hex},
            )
            assert response.status_code == 503, response.text
            assert response.json()["error"]["code"] == "demo_schema_not_ready"
        with database.session() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OrganizationModel)
                    .where(OrganizationModel.slug.like("v2-demo-%"))
                )
                == 0
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditEventModel)
                    .where(AuditEventModel.event_type == "demo.session_created")
                )
                == 0
            )
    finally:
        with database.session() as session:
            session.execute(
                text(
                    "ALTER TABLE case_resolution_events_not_migrated "
                    "RENAME TO case_resolution_events"
                )
            )


def test_verified_demo_rejects_role_escalation_and_closure_without_readback(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    app = _app(test_database_url)
    original_gateway = app.state.action_gateway
    with TestClient(app) as client:
        view = approve(client, create(client))
        changed_record = client.post(
            f"/api/demo/v2/sessions/{view['session']['session_id']}/commands",
            headers=ADMIN,
            json={
                "command": "execute",
                "role": "reviewer",
                "expected_version": view["action"]["action"]["version"],
                "resource_id": "ACT-FROM-ANOTHER-SNAPSHOT",
                "command_id": uuid4().hex,
                "reason": "Check displayed record binding.",
            },
        )
        assert changed_record.status_code == 409
        assert changed_record.json()["error"]["code"] == "demo_resource_changed"
        view = command(client, view, "execute", status=403)  # Specialist has no execute permission.
        assert view["target"]["effect_count"] == 0
        view = command(client, view, "execute", role="reviewer")
        assert not view["lifecycle"]["closure"]["eligible"]
        assert "completed" not in view["lifecycle"]["available_commands"]
        view = command(
            client, view, "close", role="reviewer", reference="SIM-MESSAGE-01", status=409
        )
        view = command(client, view, "reconcile", role="reviewer")
        assert view["target"]["effect_count"] == 1
        assert any(e["kind"] == "action_verified" for e in view["lifecycle"]["events"])
        assert view["lifecycle"]["closure"]["eligible"]
        assert view["lifecycle"]["available_commands"] == ["completed"]
        assert len(view["lifecycle"]["closure"]["verification_ids"]) == 1
        view = command(client, view, "close", role="reviewer", reference="SIM-MESSAGE-01")
        assert view["case"]["status"] == "completed"
        assert view["workspace"]["case"]["status"] == "completed"
        assert view["lifecycle"]["available_commands"] == ["reopened"]
        completion = next(e for e in view["lifecycle"]["events"] if e["kind"] == "completed")
        view = command(client, view, "reopen", reference="NEW-EVIDENCE-01")
        reopened = next(e for e in view["lifecycle"]["events"] if e["kind"] == "reopened")
        assert reopened["previous_event_id"] == completion["id"]
        assert view["case"]["status"] == "investigating"
        assert view["workspace"]["case"]["status"] == "investigating"
        assert not view["lifecycle"]["closure"]["eligible"]
        assert view["lifecycle"]["available_commands"] == []
    assert app.state.action_gateway is original_gateway


def test_timeout_target_survives_fresh_application_and_has_one_effect(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    with TestClient(_app(test_database_url)) as client:
        view = approve(client, create(client, "timeout_recovery"))
        view = command(client, view, "execute", role="reviewer")
        assert view["action"]["action"]["status"] == "outcome_unknown"
        assert view["target"]["effect_count"] == 1
        operation = view["action"]["idempotency_key"]
        view = command(client, view, "execute", role="reviewer", status=409)
        view = command(
            client, view, "close", role="reviewer", reference="SIM-MESSAGE-01", status=409
        )
    # No gateway, cache, or application object is retained across this boundary.
    with TestClient(_app(test_database_url)) as resumed:
        view = command(resumed, view, "reconcile", role="reviewer")
        assert view["action"]["action"]["status"] == "completed"
        assert view["target"]["operations"][0]["operation_id"] == operation
        assert view["target"]["effect_count"] == 1
        assert view["action"]["action"]["attempt_count"] == 1
        view = command(resumed, view, "close", role="reviewer", reference="SIM-MESSAGE-01")
        assert view["case"]["status"] == "completed"


def test_sop_revision_and_rollback_never_revive_old_approval(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    with TestClient(_app(test_database_url)) as client:
        view = approve(client, create(client, "sop_revision"))
        view = command(client, view, "publish_revision", role="policy_manager")
        assert view["policy"]["policy"]["current_version"] == 2
        view = command(client, view, "execute", role="reviewer", status=409)
        assert view["target"]["effect_count"] == 0
        view = command(client, view, "rollback", role="policy_manager")
        assert view["policy"]["policy"]["current_version"] == 3
        view = command(client, view, "execute", role="reviewer", status=409)
        assert view["target"]["effect_count"] == 0
        assert view["action"]["action"]["attempt_count"] == 0


def test_session_creation_is_idempotent_and_gateway_rejects_changed_payload(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    app = _app(test_database_url)
    with TestClient(app) as client:
        key = uuid4().hex
        body = {"scenario": "verified_reopen", "command_id": key}
        first = client.post("/api/demo/v2/sessions", headers=ADMIN, json=body)
        assert first.status_code == 201, first.text
        second = client.post("/api/demo/v2/sessions", headers=ADMIN, json=body)
        assert second.status_code == 201
        assert second.json()["data"]["session"] == first.json()["data"]["session"]
        view = approve(client, first.json()["data"])
        view = command(client, view, "execute", role="reviewer")
    with database.session() as session:
        effect = session.scalar(
            select(AuditEventModel).where(AuditEventModel.event_type == "demo.target_effect")
        )
        assert effect is not None and effect.organization_id is not None
        organization_id = effect.organization_id
        request = ActionGatewayRequest.model_validate(effect.data["request"])
    import pytest

    from app.integrations.action_gateway import ActionGatewayError
    from app.integrations.durable_demo_gateway import DurableDemoGateway

    gateway = DurableDemoGateway(database, UUID(str(organization_id)))
    duplicate = gateway.execute(
        adapter_key="deterministic_demo", provider_type="billing", request=request
    )
    assert duplicate.duplicate
    changed = request.model_copy(
        update={"parameters": {**request.parameters, "recipient": "OTHER"}}
    )
    with pytest.raises(ActionGatewayError, match="rejected"):
        gateway.execute(adapter_key="deterministic_demo", provider_type="billing", request=changed)
    assert gateway.inspect()["effect_count"] == 1
    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEventModel)
                .where(AuditEventModel.event_type == "demo.session_created")
            )
            == 1
        )
