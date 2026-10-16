"""Exposed-case preflight through real policy, decision, review and target APIs."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.evaluation.case_resolution_v2.corpus import case_path, inputs
from app.evaluation.case_resolution_v2.models import GoldenLabel
from app.evaluation.case_resolution_v2.scoring import score
from app.evaluation.case_resolution_v2.storage import digest, read_json, write_new
from app.evaluation.phase4_observation_adapter import observe
from app.evaluation.phase4_scenario_runtime import (
    case_from_input,
    product_case_id,
    target_from_input,
)
from app.integrations.action_gateway import DeterministicActionGateway
from app.persistence.case_repository import CaseRepository
from app.persistence.database import Database
from scripts.capture_phase4_run import _escalate, _publish
from tests.integration.test_case_action_api import _app, _seed_connections
from tests.integration.test_case_review_api import ADMIN, SUPERVISOR, _seed_workspace

ROOT = Path(__file__).resolve().parents[2] / "evaluations" / "case_resolution_v2_phase4"


def test_sequential_development_scopes_do_not_cross_bind(
    database: Database, test_database_url: str
) -> None:
    _, cases = inputs(ROOT, "development")
    selected = [case for case in cases if case.case_id in {"V2-DEV-001", "V2-DEV-002"}]
    _seed_workspace(database)
    _seed_connections(database)
    app = _app(test_database_url)
    app.state.action_gateway = DeterministicActionGateway(
        objects={key: value for case in selected for key, value in target_from_input(case).items()}
    )
    with TestClient(app) as client:
        for case in selected:
            with database.session() as session:
                CaseRepository(session).seed_case(
                    organization_public_id=case.tenant_id,
                    command=case_from_input(case),
                    correlation_id=f"phase4-sequential:{case.case_id}",
                )
            _publish(client, case)
            generated = client.post(
                f"/api/cases/{product_case_id(case)}/proposals",
                headers=SUPERVISOR,
                json={"expected_case_version": 1},
            )
            assert generated.status_code == 201, generated.text
            with database.session() as session:
                observe(session=session, scenario=case, decision=generated.json()["data"])


def test_exposed_scenario_runs_from_input_without_oracle(
    database: Database, test_database_url: str, tmp_path: Path
) -> None:
    _, cases = inputs(ROOT, "development")
    case = next(item for item in cases if item.case_id == "V2-DEV-017")
    _seed_workspace(database)
    _seed_connections(database)
    with database.session() as session:
        CaseRepository(session).seed_case(
            organization_public_id=case.tenant_id,
            command=case_from_input(case),
            correlation_id=f"phase4-preflight:{case.case_id}",
        )
    app = _app(test_database_url)
    gateway = DeterministicActionGateway(objects=target_from_input(case))
    app.state.action_gateway = gateway
    policy = case.policies[0]
    case_id = product_case_id(case)
    with TestClient(app) as client:
        created = client.post(
            "/api/policies",
            headers=ADMIN,
            json={
                "public_id": policy["policy_id"],
                "title": "Synthetic controlled account change",
                "description": "Published Phase 4 source authority.",
                "source": {"kind": "manual", "name": "Phase 4 input"},
                "source_text": policy["text"],
                "applicability": {
                    "decision_scope": "controlled_business_operation",
                    "case_categories": ["account_access"],
                    "products": ["all"],
                    "regions": ["all"],
                    "channels": ["all"],
                    "customer_tiers": ["all"],
                },
                "effective_from": policy["effective_from"],
                "effective_to": policy["effective_to"],
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()["data"]
        for command in ("submit-review", "publish"):
            payload = {
                "expected_policy_version": body["policy"]["version"],
                "expected_version": body["versions"][0]["record_version"],
            }
            if command == "publish":
                payload["effective_from"] = policy["effective_from"]
            response = client.post(
                f"/api/policies/{policy['policy_id']}/versions/1/{command}",
                headers=ADMIN,
                json=payload,
            )
            assert response.status_code == 200, response.text
            body = response.json()["data"]
        assert (
            client.post(
                "/api/connections/CN-0002/test",
                headers=ADMIN,
                json={"expected_version": 1},
            ).status_code
            == 200
        )
        result = client.post(
            f"/api/cases/{case_id}/proposals",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        assert result.status_code == 201, result.text
        data = result.json()["data"]
        assert data["proposal"]["state"] == "ready_for_review", {
            "policy_status": data["analysis"]["policy_status"],
            "uncertainty": data["proposal"]["uncertainty"],
            "gaps": [gap["label"] for gap in data["missing_information"]],
        }
        assert any(action["type"] == "rename_account" for action in data["proposed_actions"])
        review_response = client.post(
            f"/api/cases/{case_id}/proposals/1/reviews",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        assert review_response.status_code == 201, review_response.text
        review = review_response.json()["data"]["review"]
        reserved = client.post(
            f"/api/reviews/{review['id']}/reserve",
            headers=ADMIN,
            json={"expected_version": 1},
        )
        assert reserved.status_code == 200, reserved.text
        approved = client.post(
            f"/api/reviews/{review['id']}/decisions",
            headers=ADMIN,
            json={
                "expected_version": 2,
                "snapshot_fingerprint": review["snapshot_fingerprint"],
                "decision": "approve",
                "reason": "Input evidence and target scope checked.",
            },
        )
        assert approved.status_code == 200, approved.text
        actions = client.get("/api/actions", headers=SUPERVISOR).json()["items"]
        action = next(item for item in actions if item["case_id"] == case_id)
        executed = client.post(
            f"/api/actions/{action['id']}/execute",
            headers=SUPERVISOR,
            json={"expected_version": 1},
        )
        assert executed.status_code == 200, executed.text
        result_action = executed.json()["data"]["action"]
        assert result_action["status"] == "outcome_unknown"
        reconciled = client.post(
            f"/api/actions/{action['id']}/reconcile",
            headers=SUPERVISOR,
            json={"expected_version": result_action["version"]},
        )
        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.json()["data"]["action"]["status"] == "completed"
        assert (
            gateway.controlled_target.objects[case.evidence[0].facts["requested_target"]][
                "new_name"
            ]
            == case.evidence[0].facts["requested_new_name"]
        )
        state = client.get(f"/api/cases/{case_id}/resolution", headers=SUPERVISOR).json()
        closed = client.post(
            f"/api/cases/{case_id}/resolution",
            headers=SUPERVISOR,
            json={
                "expected_version": state["version"],
                "command_id": "phase4-dev17-close-0001",
                "kind": "completed",
                "reason": "Verified the account name and communicated the result.",
                "reference": "SYNTHETIC-MESSAGE-DEV17",
            },
        )
        assert closed.status_code == 200, closed.text
    with database.session() as session:
        observation = observe(session=session, scenario=case, decision=data)
    write_new(tmp_path / "observation.json", observation.model_dump(mode="json"))
    write_new(tmp_path / "observation-seal.json", {"sha256": digest(observation)})
    label = GoldenLabel.model_validate(
        read_json(case_path(ROOT, "development", case.case_id, "labels"))
    )
    grade = score(case, label, observation)
    assert grade.policy_correct and grade.correct_completion, {
        "failures": grade.failures,
        "observed_policy": observation.policy_status,
        "expected_policy": label.oracle.policy_expectation,
        "observed_gaps": observation.gaps,
        "expected_gaps": label.oracle.required_gaps,
        "observed_semantics": observation.semantic_assertions,
        "expected_semantics": label.semantic_assertions,
    }


@pytest.mark.parametrize("case_id", ["V2-DEV-009", "V2-DEV-010"])
def test_policy_fault_cases_are_captured_without_label_access(
    database: Database, test_database_url: str, tmp_path: Path, case_id: str
) -> None:
    _, cases = inputs(ROOT, "development")
    case = next(item for item in cases if item.case_id == case_id)
    _seed_workspace(database)
    with database.session() as session:
        CaseRepository(session).seed_case(
            organization_public_id=case.tenant_id,
            command=case_from_input(case),
            correlation_id=f"phase4-preflight:{case.case_id}",
        )
    with TestClient(_app(test_database_url)) as client:
        _publish(client, case)
        generated = client.post(
            f"/api/cases/{product_case_id(case)}/proposals",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        assert generated.status_code == 201, generated.text
        decision = generated.json()["data"]
        assert decision["proposal"]["state"] == "information_needed"
        _escalate(client, case)
    with database.session() as session:
        observation = observe(session=session, scenario=case, decision=decision)
    write_new(tmp_path / "observation.json", observation.model_dump(mode="json"))
    write_new(tmp_path / "observation-seal.json", {"sha256": digest(observation)})
    label = GoldenLabel.model_validate(
        read_json(case_path(ROOT, "development", case.case_id, "labels"))
    )
    grade = score(case, label, observation)
    assert grade.policy_correct and grade.correct_completion, {
        "failures": grade.failures,
        "observed_policy": observation.policy_status,
        "expected_policy": label.oracle.policy_expectation,
        "observed_gaps": observation.gaps,
        "expected_gaps": label.oracle.required_gaps,
        "observed_semantics": observation.semantic_assertions,
        "expected_semantics": label.semantic_assertions,
    }


def test_exposed_conflict_routes_and_is_acknowledged(
    database: Database, test_database_url: str, tmp_path: Path
) -> None:
    _, cases = inputs(ROOT, "development")
    case = next(item for item in cases if item.case_id == "V2-DEV-003")
    _seed_workspace(database)
    with database.session() as session:
        CaseRepository(session).seed_case(
            organization_public_id=case.tenant_id,
            command=case_from_input(case),
            correlation_id=f"phase4-preflight:{case.case_id}",
        )
    app = _app(test_database_url)
    policy = case.policies[0]
    case_id = product_case_id(case)
    with TestClient(app) as client:
        created = client.post(
            "/api/policies",
            headers=ADMIN,
            json={
                "public_id": policy["policy_id"],
                "title": "Synthetic settlement policy",
                "description": "Restore suspended service after verified payment.",
                "source": {"kind": "manual", "name": "Phase 4 input"},
                "source_text": policy["text"],
                "applicability": {
                    "decision_scope": "settlement_conflict_review",
                    "case_categories": ["billing_dispute"],
                    "products": ["all"],
                    "regions": ["all"],
                    "channels": ["all"],
                    "customer_tiers": ["all"],
                },
                "effective_from": policy["effective_from"],
                "effective_to": policy["effective_to"],
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()["data"]
        for command in ("submit-review", "publish"):
            payload = {
                "expected_policy_version": body["policy"]["version"],
                "expected_version": body["versions"][0]["record_version"],
            }
            if command == "publish":
                payload["effective_from"] = policy["effective_from"]
            response = client.post(
                f"/api/policies/{policy['policy_id']}/versions/1/{command}",
                headers=ADMIN,
                json=payload,
            )
            assert response.status_code == 200, response.text
            body = response.json()["data"]
        generated = client.post(
            f"/api/cases/{case_id}/proposals",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        )
        assert generated.status_code == 201, generated.text
        decision = generated.json()["data"]
        assert decision["proposal"]["state"] == "information_needed"
        assert any(
            gap["label"] == "Resolved record conflict" for gap in decision["missing_information"]
        )
        state = client.get(f"/api/cases/{case_id}/resolution", headers=SUPERVISOR).json()
        routed = client.post(
            f"/api/cases/{case_id}/resolution",
            headers=SUPERVISOR,
            json={
                "expected_version": state["version"],
                "command_id": "phase4-dev03-route-0001",
                "kind": "escalation_routed",
                "reason": "Conflicting settlement records need specialist review.",
                "reference": "USR-0002",
            },
        )
        assert routed.status_code == 200, routed.text
        state = client.get(f"/api/cases/{case_id}/resolution", headers=SUPERVISOR).json()
        ack = client.post(
            f"/api/cases/{case_id}/resolution",
            headers=SUPERVISOR,
            json={
                "expected_version": state["version"],
                "command_id": "phase4-dev03-ack-00001",
                "kind": "escalation_acknowledged",
                "reason": "Assigned supervisor accepted the investigation.",
                "reference": routed.json()["event_id"],
            },
        )
        assert ack.status_code == 200, ack.text
        state = client.get(f"/api/cases/{case_id}/resolution", headers=SUPERVISOR).json()
        message = client.post(
            f"/api/cases/{case_id}/messages",
            headers=SUPERVISOR,
            json={
                "expected_case_version": state["version"],
                "channel": "email",
                "body": "We escalated the conflicting settlement records for review.",
            },
        )
        assert message.status_code == 200, message.text
    with database.session() as session:
        observation = observe(session=session, scenario=case, decision=decision)
    write_new(tmp_path / "observation.json", observation.model_dump(mode="json"))
    write_new(tmp_path / "observation-seal.json", {"sha256": digest(observation)})
    label = GoldenLabel.model_validate(
        read_json(case_path(ROOT, "development", case.case_id, "labels"))
    )
    grade = score(case, label, observation)
    assert grade.policy_correct and grade.correct_completion, grade.model_dump()
