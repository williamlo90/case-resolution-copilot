from datetime import timedelta

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain.resolution import VerificationState
from app.integrations.action_gateway import DeterministicActionGateway, GatewayBehavior
from app.persistence.database import Database
from app.persistence.models import (
    CaseActionModel,
    CaseActionReconciliationModel,
    CaseModel,
    PolicyModel,
    utc_now,
)
from app.persistence.models.resolution import CaseResolutionEventModel
from app.persistence.quality_repository import QualityRepository
from tests.integration.test_case_action_api import _app, _approve_refund_action, _seed_connections
from tests.integration.test_case_review_api import (
    ADMIN,
    OTHER_ADMIN,
    SPECIALIST,
    SUPERVISOR,
    _seed_workspace,
)


def test_verified_closure_reopen_and_actual_escalation(
    database: Database,
    test_database_url: str,
) -> None:
    _seed_workspace(database)
    _seed_connections(database)
    app = _app(test_database_url)
    with TestClient(app) as client:
        client.post("/api/connections/CN-0001/test", headers=ADMIN, json={"expected_version": 1})
        action_id = _approve_refund_action(client)
        executed = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        )
        assert executed.status_code == 200, executed.text
        action = executed.json()["data"]["action"]
        assert action["status"] == "outcome_unknown"
        version = action["version"]
        duplicate = client.post(
            f"/api/actions/{action_id}/execute",
            headers=SUPERVISOR,
            json={"expected_version": version},
        )
        assert duplicate.status_code == 409
        manual = client.post(
            f"/api/actions/{action_id}/manual-outcome",
            headers=SUPERVISOR,
            json={
                "expected_version": version,
                "outcome": "completed",
                "reason": "A note is not a read-back",
            },
        )
        assert manual.status_code == 409
        assert client.get("/api/cases/CS-2047/resolution", headers=OTHER_ADMIN).status_code == 404
        verified = client.post(
            f"/api/actions/{action_id}/reconcile",
            headers=SUPERVISOR,
            json={"expected_version": version},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["data"]["action"]["status"] == "completed"
        assert verified.json()["data"]["attempts"][0]["side_effect_state"] == "confirmed"
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        assert state["status"] == "in_progress"
        direct = client.post(
            "/api/cases/CS-2047/status",
            headers=SUPERVISOR,
            json={"expected_version": state["version"], "status": "completed"},
        )
        assert direct.status_code == 409
        close = dict(
            expected_version=state["version"],
            command_id="close-command-0001",
            kind="completed",
            reason="Verified refund and delivered response",
            reference="SENT-MESSAGE-1",
        )
        assert (
            client.post("/api/cases/CS-2047/resolution", headers=SPECIALIST, json=close).status_code
            == 403
        )
        closed = client.post("/api/cases/CS-2047/resolution", headers=SUPERVISOR, json=close)
        assert closed.status_code == 200, closed.text
        assert (
            client.post("/api/cases/CS-2047/resolution", headers=SUPERVISOR, json=close).json()
            == closed.json()
        )
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        reopened = client.post(
            "/api/cases/CS-2047/resolution",
            headers=SUPERVISOR,
            json=dict(
                expected_version=state["version"],
                command_id="reopen-command-001",
                kind="reopened",
                reason="New customer evidence requires investigation",
                reference="EVD-NEW-1",
            ),
        )
        assert reopened.status_code == 200, reopened.text
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        assert state["events"][-1]["previous_event_id"] == closed.json()["event_id"]
        routed = client.post(
            "/api/cases/CS-2047/resolution",
            headers=SPECIALIST,
            json=dict(
                expected_version=state["version"],
                command_id="route-command-0001",
                kind="escalation_routed",
                reason="Supervisor investigation required",
                reference="USR-0002",
            ),
        )
        assert routed.status_code == 200, routed.text
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        ack = dict(
            expected_version=state["version"],
            command_id="ack-command-000001",
            kind="escalation_acknowledged",
            reason="I have accepted the case",
            reference=routed.json()["event_id"],
        )
        assert (
            client.post("/api/cases/CS-2047/resolution", headers=ADMIN, json=ack).status_code == 409
        )
        acknowledged = client.post("/api/cases/CS-2047/resolution", headers=SUPERVISOR, json=ack)
        assert acknowledged.status_code == 200, acknowledged.text
    with database.session() as session:
        assert session.scalar(select(CaseActionModel.attempt_count)) == 1
        events = list(session.scalars(select(CaseResolutionEventModel)))
        assert {e.kind for e in events} >= {
            "completed",
            "reopened",
            "action_verified",
            "escalation_routed",
            "escalation_acknowledged",
        }
        assert (
            session.scalar(select(CaseModel.status).where(CaseModel.public_id == "CS-2047"))
            == "investigating"
        )


class _MutableReadbackGateway(DeterministicActionGateway):
    observed_status = VerificationState.VERIFIED
    changed_reference = False

    def reconcile(self, **kwargs):
        result = super().reconcile(**kwargs)
        if self.changed_reference and result.receipt is not None and result.readback is not None:
            result = result.model_copy(
                update={
                    "receipt": result.receipt.model_copy(
                        update={"external_reference": "WRONG-REFERENCE"}
                    ),
                    "readback": result.readback.model_copy(
                        update={"external_reference": "WRONG-REFERENCE"}
                    ),
                }
            )
        if result.readback is not None:
            return result.model_copy(
                update={
                    "readback": result.readback.model_copy(update={"status": self.observed_status})
                }
            )
        return result


def test_timeout_effect_mismatch_and_later_invalidation(database, test_database_url):
    _seed_workspace(database)
    _seed_connections(database)
    app = _app(test_database_url)
    gateway = _MutableReadbackGateway(
        behaviors={"issue_refund": GatewayBehavior.OUTCOME_UNKNOWN_ACCEPTED}
    )
    app.state.action_gateway = gateway
    with TestClient(app) as client:
        client.post("/api/connections/CN-0001/test", headers=ADMIN, json={"expected_version": 1})
        action_id = _approve_refund_action(client)
        action = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        ).json()["data"]["action"]
        assert action["status"] == "outcome_unknown"
        gateway.observed_status = VerificationState.MISMATCH
        unknown = client.post(
            f"/api/actions/{action_id}/reconcile",
            headers=SUPERVISOR,
            json={"expected_version": action["version"]},
        ).json()["data"]["action"]
        assert unknown["status"] == "outcome_unknown"
        retry = client.post(
            f"/api/actions/{action_id}/retry",
            headers=SUPERVISOR,
            json={"expected_version": unknown["version"]},
        )
        assert retry.status_code == 409
        with database.session() as session:
            abandoned = session.scalar(select(CaseActionReconciliationModel))
            abandoned.outcome = "running"
            abandoned.checked_at = utc_now() - timedelta(minutes=6)
        gateway.observed_status = VerificationState.VERIFIED
        verified = client.post(
            f"/api/actions/{action_id}/reconcile",
            headers=SUPERVISOR,
            json={"expected_version": unknown["version"]},
        ).json()["data"]["action"]
        assert verified["status"] == "completed"
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        closed = client.post(
            "/api/cases/CS-2047/resolution",
            headers=SUPERVISOR,
            json=dict(
                expected_version=state["version"],
                command_id="close-timeout-0001",
                kind="completed",
                reason="Outcome and communication verified",
                reference="MESSAGE-1",
            ),
        )
        assert closed.status_code == 200, closed.text
        gateway.changed_reference = True
        invalidated = client.post(
            f"/api/actions/{action_id}/reconcile",
            headers=SUPERVISOR,
            json={"expected_version": verified["version"]},
        )
        assert invalidated.status_code == 200, invalidated.text
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        assert state["status"] == "investigating"
        reopened = [e for e in state["events"] if e["kind"] == "reopened"]
        assert len(reopened) == 1
        assert reopened[0]["previous_event_id"] == closed.json()["event_id"]
    with database.session() as session:
        assert session.scalar(select(CaseActionModel.attempt_count)) == 1
        report = QualityRepository(session).dashboard(
            organization_public_id="ORG-0001", category=None, limit=20
        )
        assert report.operational.reopened_cases == 1
        metrics = {m.key: m for m in report.metrics}
        assert metrics["eligible_automation"].value is None
        assert metrics["safe_automation"].numerator == 0
        assert metrics["verified_action"].numerator == 0
        assert metrics["verified_action"].denominator == 1


@pytest.mark.parametrize("mutation", ["expired", "policy", "payload"])
def test_stale_authority_blocks_external_execution(database, test_database_url, mutation):
    _seed_workspace(database)
    _seed_connections(database)
    with TestClient(_app(test_database_url)) as client:
        client.post("/api/connections/CN-0001/test", headers=ADMIN, json={"expected_version": 1})
        action_id = _approve_refund_action(client)
        with database.session() as session:
            action = session.scalar(select(CaseActionModel))
            if mutation == "expired":
                action.authorization_expires_at = utc_now() - timedelta(seconds=1)
            elif mutation == "policy":
                for policy in session.scalars(select(PolicyModel)):
                    policy.current_version += 1
            else:
                action.typed_parameters = {**action.typed_parameters, "recipient": "changed-target"}
        response = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        )
        assert response.status_code == 409, response.text
    with database.session() as session:
        assert session.scalar(select(CaseActionModel.attempt_count)) == 0


def test_additive_migration_preserves_old_case_without_fabricating_events(database):
    config = Config("alembic.ini")
    command.downgrade(config, "20260813_0024")
    _seed_workspace(database)
    with database.session() as session:
        case = session.scalar(select(CaseModel).where(CaseModel.public_id == "CS-2047"))
        case.status = "completed"
        old_id = case.id
    command.upgrade(config, "head")
    with database.session() as session:
        case = session.get(CaseModel, old_id)
        assert case.status == "completed"
        assert list(session.scalars(select(CaseResolutionEventModel))) == []
