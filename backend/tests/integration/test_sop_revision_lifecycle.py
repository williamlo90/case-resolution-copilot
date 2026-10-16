import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.integrations.action_gateway import DeterministicActionGateway, GatewayBehavior
from app.persistence.database import Database
from app.persistence.models import (
    AuditEventModel,
    BusinessObjectSnapshotModel,
    CaseActionAttemptModel,
    CaseActionModel,
    GovernedPolicyVersionModel,
    utc_now,
)
from app.persistence.policy_authority import is_current_authority
from tests.integration.test_case_action_api import _app, _approve_refund_action, _seed_connections
from tests.integration.test_case_review_api import (
    ADMIN,
    SPECIALIST,
    SUPERVISOR,
    _publish_refund_policy,
    _seed_workspace,
)


def revision(
    client: TestClient, *, restore: bool = False, scheduled: bool = False
) -> tuple[str, int, dict[str, Any]]:
    policy = client.get("/api/policies", headers=ADMIN).json()["items"][0]
    policy_id = policy["id"]
    detail = client.get(f"/api/policies/{policy_id}", headers=ADMIN).json()["data"]
    previous = min(detail["versions"], key=lambda v: v["version"])
    source = previous["source_text"]
    if not restore:
        source += (
            "\n\n## Revised authority\nAmounts above USD 100 require escalation.\n"
            '```case-resolution-rules\n{"schema_version":1,"rules":['
            '{"kind":"escalation_threshold","max_amount_minor":10000,"currency":"USD"}]}'
            "\n```"
        )
    created = client.post(
        f"/api/policies/{policy_id}/versions",
        headers=ADMIN,
        json={
            "expected_policy_version": detail["policy"]["version"],
            "source_text": source,
            "applicability": previous["applicability"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()["data"]
    version = max(body["versions"], key=lambda v: v["version"])
    number = version["version"]
    submitted = client.post(
        f"/api/policies/{policy_id}/versions/{number}/submit-review",
        headers=ADMIN,
        json={
            "expected_policy_version": body["policy"]["version"],
            "expected_version": version["record_version"],
        },
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()["data"]
    version = max(body["versions"], key=lambda v: v["version"])
    at = utc_now() + timedelta(days=1) if scheduled else utc_now()
    return (
        policy_id,
        number,
        {
            "expected_policy_version": body["policy"]["version"],
            "expected_version": version["record_version"],
            "effective_from": at.isoformat(),
        },
    )


def activate(
    client: TestClient, *, restore: bool = False, scheduled: bool = False
) -> tuple[str, int, dict[str, Any]]:
    policy_id, number, command = revision(client, restore=restore, scheduled=scheduled)
    endpoint = "schedule" if scheduled else "publish"
    response = client.post(
        f"/api/policies/{policy_id}/versions/{number}/{endpoint}", headers=ADMIN, json=command
    )
    assert response.status_code == 200, response.text
    return policy_id, number, response.json()["data"]


def reapprove(client: TestClient, old_action: str) -> str:
    state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
    moved = client.post(
        "/api/cases/CS-2047/status",
        headers=SUPERVISOR,
        json={"expected_version": state["version"], "status": "investigating"},
    )
    assert moved.status_code == 200, moved.text
    state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
    generated = client.post(
        "/api/cases/CS-2047/proposals",
        headers=SUPERVISOR,
        json={"expected_case_version": state["version"]},
    )
    assert generated.status_code == 201, generated.text
    number = generated.json()["data"]["proposal"]["version"]
    submitted = client.post(
        f"/api/cases/CS-2047/proposals/{number}/reviews",
        headers=SUPERVISOR,
        json={"expected_case_version": state["version"]},
    )
    assert submitted.status_code == 201, submitted.text
    review = submitted.json()["data"]["review"]
    reserved = client.post(
        f"/api/reviews/{review['id']}/reserve",
        headers=ADMIN,
        json={"expected_version": review["version"]},
    )
    assert reserved.status_code == 200, reserved.text
    approved = client.post(
        f"/api/reviews/{review['id']}/decisions",
        headers=ADMIN,
        json={
            "expected_version": reserved.json()["data"]["review"]["version"],
            "snapshot_fingerprint": review["snapshot_fingerprint"],
            "decision": "approve",
            "reason": "Re-evaluated and approved against the replacement immutable SOP.",
        },
    )
    assert approved.status_code == 200, approved.text
    items = client.get("/api/actions", headers=SUPERVISOR).json()["items"]
    return str(next(a["id"] for a in items if a["id"] != old_action))


def test_policy_revision_invalidates_approval_and_rollback_does_not_resurrect_it(
    database: Database,
    test_database_url: str,
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    with TestClient(_app(test_database_url)) as client:
        action_id = _approve_refund_action(client)
        activate(client)
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        revised = client.post(
            "/api/cases/CS-2047/proposals",
            headers=SUPERVISOR,
            json={"expected_case_version": state["version"]},
        )
        assert revised.status_code == 201, revised.text
        assert revised.json()["data"]["proposal"]["state"] == "information_needed"
        assert any(
            "escalation_threshold" in gap["description"]
            for gap in revised.json()["data"]["missing_information"]
        )
        blocked = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        )
        assert blocked.status_code == 409, blocked.text
        activate(client, restore=True)
        blocked = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        )
        assert blocked.status_code == 409, blocked.text
        new_action = reapprove(client, action_id)
        detail = client.get(f"/api/actions/{new_action}", headers=SUPERVISOR).json()["data"]
        assert detail["execution_blocker"] is None
    with database.session() as session:
        assert session.scalar(select(func.count(CaseActionAttemptModel.id))) == 0
        versions = list(
            session.scalars(
                select(GovernedPolicyVersionModel).order_by(GovernedPolicyVersionModel.version)
            )
        )
        assert len(versions) == 3
        assert versions[0].content_hash == versions[2].content_hash
        assert versions[0].id != versions[2].id
        assert all(v.immutable for v in versions)


def test_scheduled_version_boundary_and_authorized_publisher(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    with TestClient(_app(test_database_url)) as client:
        action_id = _approve_refund_action(client)
        policy_id, number, command = revision(client, scheduled=True)
        denied = client.post(
            f"/api/policies/{policy_id}/versions/{number}/schedule",
            headers=SPECIALIST,
            json=command,
        )
        assert denied.status_code == 403
        response = client.post(
            f"/api/policies/{policy_id}/versions/{number}/schedule", headers=ADMIN, json=command
        )
        assert response.status_code == 200, response.text
        # A pending draft/schedule must not discard still-current approval.
        detail = client.get(f"/api/actions/{action_id}", headers=SUPERVISOR).json()["data"]
        assert detail["execution_blocker"] is None
    with database.session() as session:
        versions = list(
            session.scalars(
                select(GovernedPolicyVersionModel).order_by(GovernedPolicyVersionModel.version)
            )
        )
        boundary = versions[1].effective_from
        assert boundary is not None
        assert is_current_authority(session, versions[0].id, boundary - timedelta(microseconds=1))
        assert not is_current_authority(session, versions[0].id, boundary)
        assert is_current_authority(session, versions[1].id, boundary)
        versions[1].effective_to = boundary + timedelta(days=1)
        session.flush()
        assert not is_current_authority(session, versions[0].id, boundary + timedelta(days=1))
        assert not is_current_authority(session, versions[1].id, boundary + timedelta(days=1))


def test_timeout_then_policy_rollback_resumes_lookup_without_second_effect(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    app = _app(test_database_url)
    app.state.action_gateway = DeterministicActionGateway(
        behaviors={"issue_refund": GatewayBehavior.OUTCOME_UNKNOWN_ACCEPTED}
    )
    with TestClient(app) as client:
        action_id = _approve_refund_action(client)
        executed = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        )
        assert executed.status_code == 200, executed.text
        pending = executed.json()["data"]["action"]
        assert pending["status"] == "outcome_unknown"
        with database.session() as session:
            original_key = session.scalar(select(CaseActionModel.idempotency_key))
        activate(client)
        activate(client, restore=True)
        replacement_id = reapprove(client, action_id)
        replacement = client.post(
            f"/api/actions/{replacement_id}/execute",
            headers=SUPERVISOR,
            json={"expected_version": 1},
        )
        assert replacement.status_code == 409, replacement.text
        assert replacement.json()["error"]["details"]["blocker"] == "duplicate"
        # Reconstruct the API service as a config restart; external target is retained.
        resumed_app = _app(test_database_url)
        resumed_app.state.action_gateway = app.state.action_gateway
        with TestClient(resumed_app) as resumed:
            found = resumed.post(
                f"/api/actions/{action_id}/reconcile",
                headers=SUPERVISOR,
                json={"expected_version": pending["version"]},
            )
            assert found.status_code == 200, found.text
            completed = found.json()["data"]["action"]
            assert completed["status"] == "completed"
            duplicate = resumed.post(
                f"/api/actions/{action_id}/execute",
                headers=SUPERVISOR,
                json={"expected_version": completed["version"]},
            )
            assert duplicate.status_code == 409
    with database.session() as session:
        assert session.scalar(select(func.count(CaseActionAttemptModel.id))) == 1
        assert (session.scalar(select(func.count(AuditEventModel.id))) or 0) > 0
        action = session.scalar(
            select(CaseActionModel).where(CaseActionModel.public_id == action_id)
        )
        assert action is not None
        assert action.idempotency_key == original_key


def test_changed_evidence_after_approval_cannot_dispatch(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    with TestClient(_app(test_database_url)) as client:
        action_id = _approve_refund_action(client)
        with database.session() as session:
            for context in session.scalars(select(BusinessObjectSnapshotModel)):
                context.version += 1
                context.fields = {**context.fields, "delivery_state": "started"}
        response = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        )
        assert response.status_code == 409, response.text
    with database.session() as session:
        assert session.scalar(select(func.count(CaseActionAttemptModel.id))) == 0


@pytest.mark.skipif(os.environ.get("PHASE3_CONCURRENCY") != "1", reason="Isolated CI only")
def test_concurrent_publication_and_approval_never_authorize_stale_dispatch(
    database: Database, test_database_url: str
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    app = _app(test_database_url)
    with TestClient(app) as client:
        _publish_refund_policy(client)
        assert (
            client.post(
                "/api/cases/CS-2047/proposals",
                headers=SUPERVISOR,
                json={"expected_case_version": 1},
            ).status_code
            == 201
        )
        submitted = client.post(
            "/api/cases/CS-2047/proposals/1/reviews",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        review = submitted.json()["data"]["review"]
        assert (
            client.post(
                f"/api/reviews/{review['id']}/reserve", headers=ADMIN, json={"expected_version": 1}
            ).status_code
            == 200
        )
        policy_id, number, command = revision(client)
        barrier = Barrier(2)

        def publish() -> Any:
            barrier.wait(timeout=10)
            return client.post(
                f"/api/policies/{policy_id}/versions/{number}/publish", headers=ADMIN, json=command
            )

        def approve() -> Any:
            barrier.wait(timeout=10)
            return client.post(
                f"/api/reviews/{review['id']}/decisions",
                headers=ADMIN,
                json={
                    "expected_version": 2,
                    "snapshot_fingerprint": review["snapshot_fingerprint"],
                    "decision": "approve",
                    "reason": "Frozen snapshot approval racing SOP publication.",
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            publication, approval = pool.submit(publish), pool.submit(approve)
            assert publication.result(timeout=30).status_code == 200
            approved = approval.result(timeout=30)
        assert approved.status_code in {200, 409}, approved.text
        actions = client.get("/api/actions", headers=SUPERVISOR).json()["items"]
        for action in actions:
            response = client.post(
                f"/api/actions/{action['id']}/execute",
                headers=SUPERVISOR,
                json={"expected_version": action["version"]},
            )
            assert response.status_code == 409
    with database.session() as session:
        assert session.scalar(select(func.count(CaseActionAttemptModel.id))) == 0
