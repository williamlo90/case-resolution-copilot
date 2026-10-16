"""One bounded, synthetic API/DB journey. This is not the V2 holdout adapter."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.evaluation.case_resolution_v2.storage import digest, file_digest, write_new
from app.evaluation.phase4_operations import latency_summary, simulated_reopen_summary
from app.integrations.action_gateway import DeterministicActionGateway, GatewayBehavior
from app.persistence.database import Database
from app.persistence.models import CaseActionModel
from app.persistence.models.resolution import CaseResolutionEventModel
from tests.integration.test_case_action_api import _app, _approve_refund_action, _seed_connections
from tests.integration.test_case_review_api import ADMIN, SUPERVISOR, _seed_workspace


class RecordedClient(TestClient):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: Any, **kwargs: Any) -> httpx2.Response:
        started = perf_counter()
        response = super().request(method, url, **kwargs)
        # Only synthetic response bodies; never persist request headers, settings or DB URLs.
        self.calls.append(
            dict(
                method=method,
                path=str(url),
                status=response.status_code,
                duration_ms=(perf_counter() - started) * 1000,
                response=response.json(),
            )
        )
        return response


def test_record_timeout_readback_closure_and_simulated_followup(
    database: Database,
    test_database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = Path(os.environ.get("PHASE4_EVIDENCE_DIR", str(tmp_path / "evidence")))
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Evidence must use a new output directory")
    backend = Path(__file__).resolve().parents[2]
    source_paths = sorted((backend / "app").rglob("*.py")) + [Path(__file__)]
    sources = {str(path.relative_to(backend)): file_digest(path) for path in source_paths}
    write_new(
        output / "run-contract.json",
        dict(
            profile="development_api_testclient_postgresql_demo_gateway",
            started_at=datetime.now(UTC).isoformat(),
            source_sha256=digest(sources),
            sources=sources,
            fixture="existing CS-2047 exposed regression; not a new holdout case",
            provider_call_budget=0,
            provider_cost_budget_usd=0,
            followup="simulated event clock, reopen day 7, final observation day 30",
            oracle="asserted lifecycle invariants only; not scored by V2 semantic oracle",
        ),
    )
    _seed_workspace(database)
    _seed_connections(database)
    app = _app(test_database_url)
    app.state.action_gateway = DeterministicActionGateway(
        behaviors={"issue_refund": GatewayBehavior.OUTCOME_UNKNOWN_ACCEPTED}
    )
    started = perf_counter()
    with RecordedClient(app) as client:
        assert (
            client.post(
                "/api/connections/CN-0001/test", headers=ADMIN, json={"expected_version": 1}
            ).status_code
            == 200
        )
        action_id = _approve_refund_action(client)
        executed = client.post(
            f"/api/actions/{action_id}/execute", headers=SUPERVISOR, json={"expected_version": 1}
        )
        assert executed.status_code == 200
        action = executed.json()["data"]["action"]
        assert action["status"] == "outcome_unknown"
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
        assert verified.status_code == 200
        assert verified.json()["data"]["action"]["status"] == "completed"
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        closed = client.post(
            "/api/cases/CS-2047/resolution",
            headers=SUPERVISOR,
            json=dict(
                expected_version=state["version"],
                command_id="phase4-close-00001",
                kind="completed",
                reason="Verified synthetic refund and sent response",
                reference="SYNTHETIC-SENT-MESSAGE-1",
            ),
        )
        assert closed.status_code == 200
        with database.session() as session:
            completion = session.scalar(
                select(CaseResolutionEventModel).where(CaseResolutionEventModel.kind == "completed")
            )
            assert completion is not None
            completed_at = completion.occurred_at
            completion_id = str(completion.id)
        monkeypatch.setattr(
            "app.persistence.resolution_repository.utc_now",
            lambda: completed_at + timedelta(days=7),
        )
        state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        reopened = client.post(
            "/api/cases/CS-2047/resolution",
            headers=SUPERVISOR,
            json=dict(
                expected_version=state["version"],
                command_id="phase4-reopen-0001",
                kind="reopened",
                reason="New synthetic evidence on simulated day 7",
                reference="SYNTHETIC-NEW-EVIDENCE-1",
            ),
        )
        assert reopened.status_code == 200
        # Observe the complete declared synthetic timeline; this is not elapsed production time.
        monkeypatch.setattr(
            "app.persistence.resolution_repository.utc_now",
            lambda: completed_at + timedelta(days=30),
        )
        final_state = client.get("/api/cases/CS-2047/resolution", headers=SUPERVISOR).json()
        assert final_state["status"] == "investigating"
    elapsed_ms = (perf_counter() - started) * 1000
    with database.session() as session:
        persisted = session.scalar(select(CaseActionModel))
        assert persisted is not None and persisted.attempt_count == 1
        events = list(session.scalars(select(CaseResolutionEventModel)))
        reopened_events = [event for event in events if event.kind == "reopened"]
        assert len(reopened_events) == 1
        event = reopened_events[0]
        assert str(event.previous_event_id) == completion_id
        assert event.case_id == completion.case_id
        assert event.organization_id == completion.organization_id
        verified_events = [item for item in events if item.kind == "action_verified"]
        assert len(verified_events) == 1
        raw_events = [
            dict(
                id=str(item.id),
                kind=item.kind,
                case_id=str(item.case_id),
                organization_id=str(item.organization_id),
                occurred_at=item.occurred_at.isoformat(),
                previous_event_id=str(item.previous_event_id) if item.previous_event_id else None,
                data=item.data,
            )
            for item in events
        ]
        reopened_at = event.occurred_at
    trace = dict(api_calls=client.calls, events=raw_events, end_to_end_ms=elapsed_ms)
    write_new(output / "observations.json", trace)
    write_new(output / "observation-seal.json", dict(observations_sha256=digest(trace)))
    write_new(
        output / "operations-report.json",
        dict(
            profile="exposed_regression_not_holdout",
            scheduled_journeys=1,
            completed_test_journeys=1,
            verified_actions=dict(numerator=1, denominator=1),
            completed_lifecycle_events=1,
            reopened_lifecycle_events=1,
            final_open_cases=1,
            duplicate_dispatches_blocked=1,
            execution_attempts=1,
            policy_correctness=None,
            correct_completion=None,
            explanation="Lifecycle proof does not establish V2 semantic correctness",
            eligible_automation=dict(numerator=0, denominator=0, value=None),
            simulated_followup=[
                simulated_reopen_summary(
                    completed_at=completed_at,
                    reopened_at=reopened_at,
                    followed_until=completed_at + timedelta(days=30),
                    days=days,
                )
                for days in (7, 30)
            ],
            latency=dict(
                api_testclient=latency_summary([call["duration_ms"] for call in client.calls]),
                end_to_end=latency_summary([elapsed_ms]),
                worker=latency_summary([]),
                provider=latency_summary([]),
            ),
            costs=dict(
                provider_calls=0,
                tokens=0,
                provider_usd=0,
                price_snapshot=None,
                price_reason="no provider used",
                infrastructure_usd=None,
                infrastructure_estimate_usd=None,
                verified_correct_resolutions=None,
                provider_per_verified_resolution_usd=None,
                total_per_verified_resolution_usd=None,
            ),
            observations_sha256=digest(trace),
        ),
    )
