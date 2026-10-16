"""Input-only synthetic product capture for an isolated CI PostgreSQL runner.

This module refuses an unisolated process and requires a corpus bundle without labels.
Scoring happens in a separate job after observation sealing.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx2
from fastapi.testclient import TestClient

from app.analysis.deterministic_decision_engine import (
    DECISION_MODEL_VERSION,
    DECISION_PROMPT_VERSION,
)
from app.config import Settings
from app.evaluation.case_resolution_v2.corpus import inputs
from app.evaluation.case_resolution_v2.runner import declare_run, seal_observations
from app.evaluation.case_resolution_v2.storage import digest, write_new
from app.evaluation.phase4_observation_adapter import observe
from app.evaluation.phase4_operations import latency_summary, simulated_reopen_summary
from app.evaluation.phase4_scenario_runtime import (
    case_from_input,
    product_case_id,
    target_from_input,
)
from app.integrations.action_gateway import DeterministicActionGateway
from app.integrations.connection_seed import deterministic_connection_seeds
from app.main import create_app
from app.persistence.case_repository import CaseRepository
from app.persistence.connection_repository import ConnectionRepository
from app.persistence.database import Database
from app.persistence.models import MembershipModel, OrganizationModel
from app.security.authentication import DETERMINISTIC_ACTORS, DeterministicAuthProvider

ADMIN = {"X-Actor-ID": "USR-0003"}
SUPERVISOR = {"X-Actor-ID": "USR-0002"}


class RecordedClient(TestClient):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.durations_ms: list[float] = []

    def request(self, method: str, url: Any, **kwargs: Any) -> httpx2.Response:
        started = perf_counter()
        result = super().request(method, url, **kwargs)
        self.durations_ms.append((perf_counter() - started) * 1000)
        return result


def _required(response: Any, expected: int) -> dict[str, Any]:
    if response.status_code != expected:
        raise RuntimeError(f"Product API returned {response.status_code}")
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError("Product API returned an invalid envelope")
    return value


def _seed_baseline(database: Database) -> None:
    with database.session() as session:
        organization = OrganizationModel(
            public_id="ORG-0001", name="Phase 4 Synthetic", slug="phase4-synthetic"
        )
        session.add(organization)
        session.flush()
        session.add_all(
            MembershipModel(
                public_id=public_id,
                organization_id=organization.id,
                subject_id=public_id,
                name=f"Synthetic {role}",
                email=f"{public_id.lower()}@example.test",
                role=role,
                status="active",
            )
            for public_id, role in (
                ("USR-0001", "specialist"),
                ("USR-0002", "supervisor"),
                ("USR-0003", "administrator"),
            )
        )
        connections = ConnectionRepository(session)
        for command in deterministic_connection_seeds():
            connections.seed(
                organization_public_id="ORG-0001",
                command=command,
                correlation_id=f"phase4:{command.public_id}",
            )


def _publish(client: TestClient, scenario: Any) -> None:
    category = case_from_input(scenario).category.value
    scope = "phase4:" + scenario.family_id.replace(":", ":")
    for policy in scenario.policies:
        policy_id = policy["policy_id"]
        created = _required(
            client.post(
                "/api/policies",
                headers=ADMIN,
                json={
                    "public_id": policy_id,
                    "title": scenario.family_id,
                    "description": "Synthetic source policy for a sealed evaluation family.",
                    "source": {"kind": "manual", "name": "Phase 4 input"},
                    "source_text": policy["text"],
                    "applicability": {
                        "decision_scope": scope,
                        "case_categories": [category],
                        "products": ["all"],
                        "regions": ["all"],
                        "channels": ["all"],
                        "customer_tiers": ["all"],
                    },
                    "effective_from": policy["effective_from"],
                    "effective_to": policy["effective_to"],
                },
            ),
            201,
        )["data"]
        for command in ("submit-review", "publish"):
            body: dict[str, Any] = {
                "expected_policy_version": created["policy"]["version"],
                "expected_version": created["versions"][0]["record_version"],
            }
            if command == "publish":
                body["effective_from"] = policy["effective_from"]
            created = _required(
                client.post(
                    f"/api/policies/{policy_id}/versions/1/{command}",
                    headers=ADMIN,
                    json=body,
                ),
                200,
            )["data"]


def _resolution(client: TestClient, case_id: str) -> dict[str, Any]:
    return _required(client.get(f"/api/cases/{case_id}/resolution", headers=SUPERVISOR), 200)


def _command(
    client: TestClient,
    *,
    case_id: str,
    command_id: str,
    kind: str,
    reason: str,
    reference: str,
) -> dict[str, Any]:
    state = _resolution(client, case_id)
    return _required(
        client.post(
            f"/api/cases/{case_id}/resolution",
            headers=SUPERVISOR,
            json={
                "expected_version": state["version"],
                "command_id": command_id,
                "kind": kind,
                "reason": reason,
                "reference": reference,
            },
        ),
        200,
    )


def _resolve(client: TestClient, scenario: Any) -> dict[str, Any]:
    case_id = product_case_id(scenario)
    review = _required(
        client.post(
            f"/api/cases/{case_id}/proposals/1/reviews",
            headers=SUPERVISOR,
            json={"expected_case_version": 1},
        ),
        201,
    )["data"]["review"]
    _required(
        client.post(
            f"/api/reviews/{review['id']}/reserve",
            headers=ADMIN,
            json={"expected_version": 1},
        ),
        200,
    )
    _required(
        client.post(
            f"/api/reviews/{review['id']}/decisions",
            headers=ADMIN,
            json={
                "expected_version": 2,
                "snapshot_fingerprint": review["snapshot_fingerprint"],
                "decision": "approve",
                "reason": "Synthetic source, scope and target checked.",
            },
        ),
        200,
    )
    queue = _required(client.get("/api/actions", headers=SUPERVISOR), 200)["items"]
    action = next(item for item in queue if item["case_id"] == case_id)
    first = _required(
        client.post(
            f"/api/actions/{action['id']}/execute",
            headers=SUPERVISOR,
            json={"expected_version": 1},
        ),
        200,
    )["data"]["action"]
    duplicate_blocked = None
    if "duplicate_action" in scenario.tags:
        duplicate = client.post(
            f"/api/actions/{action['id']}/execute",
            headers=SUPERVISOR,
            json={"expected_version": first["version"]},
        )
        duplicate_blocked = duplicate.status_code == 409
    if first["status"] == "outcome_unknown":
        final = _required(
            client.post(
                f"/api/actions/{action['id']}/reconcile",
                headers=SUPERVISOR,
                json={"expected_version": first["version"]},
            ),
            200,
        )["data"]["action"]
    else:
        final = first
    if final["status"] == "completed":
        _command(
            client,
            case_id=case_id,
            command_id=f"phase4-close-{scenario.case_id}",
            kind="completed",
            reason="Verified synthetic target readback and communicated the result.",
            reference=f"SYNTHETIC-MESSAGE-{scenario.case_id}",
        )
    return {"duplicate_blocked": duplicate_blocked, "action_status": final["status"]}


def _escalate(client: TestClient, scenario: Any) -> dict[str, Any]:
    case_id = product_case_id(scenario)
    route = _command(
        client,
        case_id=case_id,
        command_id=f"phase4-route-{scenario.case_id}",
        kind="escalation_routed",
        reason="The product blocked a consequential action pending specialist review.",
        reference="USR-0002",
    )
    _command(
        client,
        case_id=case_id,
        command_id=f"phase4-ack-{scenario.case_id}",
        kind="escalation_acknowledged",
        reason="Assigned supervisor accepted the investigation.",
        reference=route["event_id"],
    )
    state = _resolution(client, case_id)
    _required(
        client.post(
            f"/api/cases/{case_id}/messages",
            headers=SUPERVISOR,
            json={
                "expected_case_version": state["version"],
                "channel": "email",
                "body": "We escalated the source or policy issue for review.",
            },
        ),
        200,
    )
    return {"escalation_acknowledged": True}


def _followup(client: TestClient, scenario: Any, completed_at: datetime) -> list[dict[str, Any]]:
    if "reopen" not in scenario.tags:
        return []
    import app.persistence.resolution_repository as lifecycle

    original_clock = lifecycle.utc_now  # type: ignore[attr-defined]
    case_id = product_case_id(scenario)
    try:
        lifecycle.utc_now = lambda: completed_at + timedelta(days=7)  # type: ignore[attr-defined]
        _command(
            client,
            case_id=case_id,
            command_id=f"phase4-reopen-{scenario.case_id}",
            kind="reopened",
            reason="New contradictory evidence in synthetic day-seven followup.",
            reference=f"FOLLOWUP-{scenario.case_id}",
        )
        lifecycle.utc_now = lambda: completed_at + timedelta(days=30)  # type: ignore[attr-defined]
        state = _resolution(client, case_id)
        reopened_at = next(
            datetime.fromisoformat(item["at"].replace("Z", "+00:00"))
            for item in state["events"]
            if item["kind"] == "reopened"
        )
        return [
            simulated_reopen_summary(
                completed_at=completed_at,
                reopened_at=reopened_at,
                followed_until=completed_at + timedelta(days=30),
                days=day,
            )
            for day in (7, 30)
        ]
    finally:
        lifecycle.utc_now = original_clock  # type: ignore[attr-defined]


def capture(root: Path, split: str, output: Path, revision: str, database_url: str) -> None:
    if os.environ.get("PHASE4_ISOLATED_RUN") != "1":
        raise RuntimeError("Full Phase 4 capture is restricted to isolated CI")
    if (root / split / "labels").exists():
        raise RuntimeError("The runtime bundle must not contain oracle labels")
    spec, cases = inputs(root, split)
    config = {
        "model_version": DECISION_MODEL_VERSION,
        "prompt_version": DECISION_PROMPT_VERSION,
        "runtime_adapter_version": "phase4-product-postgres-1",
        "policy_snapshot_sha256": digest([case.policies for case in cases]),
        "environment": "isolated-ci-postgresql-synthetic-target",
        "seed": spec.seed,
    }
    declare_run(
        root=root,
        split=split,
        output=output,
        case_ids=[case.case_id for case in cases],
        execution_profile="deterministic_product",
        product_revision=revision,
        config=config,
    )
    database = Database(database_url)
    _seed_baseline(database)
    app = create_app(Settings(environment="test", database_url=database_url, _env_file=None))
    app.state.auth_provider = DeterministicAuthProvider(DETERMINISTIC_ACTORS)
    gateway = DeterministicActionGateway()
    app.state.action_gateway = gateway
    timings: list[float] = []
    followups: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    duplicate_checks = 0
    with RecordedClient(app) as client:
        for connection in ("CN-0001", "CN-0002"):
            _required(
                client.post(
                    f"/api/connections/{connection}/test",
                    headers=ADMIN,
                    json={"expected_version": 1},
                ),
                200,
            )
        for scenario in cases:
            started = perf_counter()
            stage = "seed_case"
            try:
                with database.session() as session:
                    CaseRepository(session).seed_case(
                        organization_public_id=scenario.tenant_id,
                        command=case_from_input(scenario),
                        correlation_id=f"phase4:{scenario.case_id}",
                    )
                gateway.controlled_target.objects.update(target_from_input(scenario))
                stage = "publish_policy"
                _publish(client, scenario)
                stage = "propose"
                decision = _required(
                    client.post(
                        f"/api/cases/{product_case_id(scenario)}/proposals",
                        headers=SUPERVISOR,
                        json={"expected_case_version": 1},
                    ),
                    201,
                )["data"]
                if decision["proposal"]["state"] == "ready_for_review" and any(
                    action["review_required"] for action in decision["proposed_actions"]
                ):
                    stage = "review_execute_close"
                    lane = _resolve(client, scenario)
                    duplicate_checks += int(lane["duplicate_blocked"] is True)
                else:
                    stage = "escalate"
                    lane = _escalate(client, scenario)
                stage = "observe"
                with database.session() as session:
                    observation = observe(session=session, scenario=scenario, decision=decision)
                if "reopen" in scenario.tags and observation.completion:
                    stage = "simulated_followup"
                    followups.extend(
                        _followup(client, scenario, observation.completion.occurred_at)
                    )
                stage = "persist_observation"
                write_new(output / f"{scenario.case_id}.json", observation.model_dump(mode="json"))
                timings.append((perf_counter() - started) * 1000)
            except Exception as exc:
                failures.append(
                    {"case_id": scenario.case_id, "stage": stage, "error_type": type(exc).__name__}
                )
                if not (output / f"{scenario.case_id}.json").exists():
                    write_new(
                        output / f"{scenario.case_id}.json",
                        {"capture_status": "invalid", "capture_error": type(exc).__name__},
                    )
    seal_observations(
        root=root,
        split=split,
        output=output,
        execution_profile="deterministic_product",
        product_revision=revision,
        config=config,
    )
    write_new(
        output / "operations-report.json",
        {
            "profile": "isolated_ci_postgresql_synthetic_target",
            "scheduled": len(cases),
            "observed": len(timings),
            "invalid": len(failures),
            "failures": failures,
            "duplicate_dispatches_blocked": duplicate_checks,
            "simulated_followup": followups,
            "latency": {
                "end_to_end_case": latency_summary(timings),
                "api": latency_summary(client.durations_ms),
                "worker": latency_summary([]),
                "provider": latency_summary([]),
            },
            "model_token_usage": 0,
            "provider_calls": 0,
            "measured_provider_cost_usd": 0,
            "infrastructure_cost_estimate_usd": None,
            "scope": "Synthetic target and CI PostgreSQL; not a live payment or identity provider.",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "regression", "holdout"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    database_url = os.environ.get("PHASE4_DATABASE_URL")
    if not database_url:
        raise RuntimeError("PHASE4_DATABASE_URL is required")
    capture(args.root, args.split, args.output, args.revision, database_url)


if __name__ == "__main__":
    main()
