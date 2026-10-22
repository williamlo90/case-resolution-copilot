"""Stateless HTTP coordinator; all mutable state/evidence is persisted in PostgreSQL."""

from __future__ import annotations

import copy
import os
from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.identity import current_actor
from app.domain.controlled_operations import OPERATIONS
from app.domain.identity import (
    ROLE_PERMISSIONS,
    ActorContext,
    ActorKind,
    AuthenticationMode,
    MemberRole,
)
from app.evaluation.case_resolution_v2.models import Observation, Scenario
from app.evaluation.case_resolution_v2.storage import digest
from app.evaluation.phase4_observation_adapter import observe
from app.evaluation.phase4_scenario_runtime import product_case_id
from app.persistence.database import Database
from app.persistence.models import CaseProposedActionModel

from .context import internal_actor, manual_engine
from .manual import ManualEngine
from .storage import insert, record

router = APIRouter(prefix="/api/operator-study", tags=["operator study"])


def instant(session: Session) -> datetime:
    value = session.scalar(select(func.clock_timestamp()))
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Authoritative database clock unavailable")
    return value


def study_actor(role: str) -> ActorContext:
    selected = MemberRole.ADMINISTRATOR if role == "administrator" else MemberRole.SUPERVISOR
    return ActorContext(
        actor_id="USR-0003" if role == "administrator" else "USR-0002",
        organization_id="ORG-0001",
        name=f"Synthetic study {role}",
        kind=ActorKind.MEMBER,
        role=selected,
        permissions=ROLE_PERMISSIONS[selected],
        authentication_mode=AuthenticationMode.PROVIDER,
    )


def access(request: Request, actor: ActorContext) -> Database:
    if not request.app.state.settings.operator_study_enabled or actor.actor_id != "STUDY-OWNER":
        from app.api.errors import AppError

        raise AppError(
            code="study_access_denied",
            message="This study is not available to this account.",
            status_code=403,
        )
    return cast(Database, request.app.state.database)


def packet_name(packet: str) -> str:
    if packet not in {"primary", "practice", "training"}:
        raise HTTPException(status_code=404, detail="Unknown study packet")
    return packet


@router.get("/state")
def state(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    packet: str = "practice",
) -> dict[str, Any]:
    db = access(request, actor)
    with db.session() as session:
        row = record(session, "session", packet_name(packet))
        bundle = record(session, "packet", packet)
        if row is None or bundle is None:
            return {"ready": False, "detail": "Study fixtures have not been initialized."}
        value = row.value
        active = value.get("active")
        snapshot = None
        if active:
            snapshot = {key: active[key] for key in ("case_id", "pair_id", "condition", "sequence")}
            snapshot["scenario"] = bundle.value["cases"][active["case_id"]]
            snapshot["elapsed_seconds"] = (
                instant(session) - datetime.fromisoformat(active["started_at"])
            ).total_seconds()
            snapshot["submitted"] = active.get("submitted")
            snapshot["decision"] = active.get("decision")
            if active.get("decision"):
                ids = [item["id"] for item in active["decision"]["proposed_actions"]]
                snapshot["actions"] = [
                    {"type": item.type, "parameters": item.parameters}
                    for item in session.scalars(
                        select(CaseProposedActionModel).where(
                            CaseProposedActionModel.public_id.in_(ids),
                            CaseProposedActionModel.type.in_(OPERATIONS),
                        )
                    )
                ]
        index = value["index"]
        return {
            "completed": index,
            "total": len(bundle.value["order"]),
            "next": bundle.value["order"][index] if index < len(bundle.value["order"]) else None,
            "active": bool(active),
            "active_task": snapshot,
            "ready": value.get("ready", False),
            "practice": packet != "primary",
            "profile": request.app.state.settings.model_provider,
            "source_revision": os.environ.get("VERCEL_GIT_COMMIT_SHA", "local-test"),
            "last_command": value.get("last_command"),
        }


class Coordinator:
    def __init__(
        self,
        request: Request,
        db: Database,
        session: Session,
        value: dict[str, Any],
        bundle: dict[str, Any],
        packet: str,
    ) -> None:
        self.request, self.db, self.session = request, db, session
        self.value, self.bundle, self.packet = value, bundle, packet
        self.active: dict[str, Any] = value.get("active") or {}

    async def call(
        self, method: str, path: str, body: dict[str, Any] | None = None, role: str = "supervisor"
    ) -> dict[str, Any]:
        token = internal_actor.set(study_actor(role))
        begin = instant(self.session)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.request.app),
                base_url="http://study.internal",
            ) as client:
                response = await client.request(method, path, json=body)
        finally:
            internal_actor.reset(token)
        result = response.json()
        self.active.setdefault("api_log", []).append(
            {
                "method": method,
                "path": path,
                "body": body,
                "role": role,
                "status": response.status_code,
                "response": result,
            }
        )
        self.active.setdefault("api_samples", []).append(
            {
                "path": path,
                "method": method,
                "status": response.status_code,
                "milliseconds": (instant(self.session) - begin).total_seconds() * 1000,
                "inside_timed_interval": "finished_at" not in self.active,
            }
        )
        if response.status_code >= 400:
            raise ValueError(
                f"Product rejected command ({response.status_code}): {str(result)[:700]}"
            )
        return cast(dict[str, Any], result)

    async def lifecycle(
        self, scenario: Scenario, kind: str, reason: str, reference: str
    ) -> dict[str, Any]:
        url = f"/api/cases/{product_case_id(scenario)}/resolution"
        current = await self.call("GET", url)
        return await self.call(
            "POST",
            url,
            {
                "expected_version": current["version"],
                "command_id": str(uuid4()),
                "kind": kind,
                "reason": reason,
                "reference": reference,
            },
        )

    def actions(self) -> list[dict[str, Any]]:
        ids = [item["id"] for item in self.active["decision"]["proposed_actions"]]
        with self.db.session() as session:
            rows = session.scalars(
                select(CaseProposedActionModel).where(
                    CaseProposedActionModel.public_id.in_(ids),
                    CaseProposedActionModel.type.in_(OPERATIONS),
                )
            )
            return [{"type": row.type, "parameters": row.parameters} for row in rows]

    async def command(self, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        now = instant(self.session)
        runtime = {
            "source_revision": os.environ.get("VERCEL_GIT_COMMIT_SHA", "local-test"),
            "model_provider": self.request.app.state.settings.model_provider,
            "embedding_provider": self.request.app.state.settings.embedding_provider,
            "clock": "postgres-clock_timestamp",
        }
        if self.packet == "primary" and self.value.get("runtime", runtime) != runtime:
            raise ValueError(
                "Study runtime changed; restore the frozen deployment before continuing"
            )
        if kind == "start":
            if (
                self.active
                or not self.value.get("ready")
                or self.value["index"] >= len(self.bundle["order"])
            ):
                raise ValueError("Study not ready, already active, or complete")
            self.value["runtime"] = runtime
            row = self.bundle["order"][self.value["index"]]
            scenario = Scenario.model_validate(self.bundle["cases"][row["case_id"]])
            if not scenario.as_of <= now <= scenario.deadline:
                raise ValueError("Outside the frozen scenario time window")
            self.active = {
                **row,
                "started_at": now.isoformat(),
                "runtime": runtime,
                "started_ns": int(now.timestamp() * 1e9),
                "clock": "postgres-clock_timestamp",
                "browser": body.get("browser", "unknown"),
                "events": [],
                "api_log": [],
                "api_samples": [],
                "submitted": None,
                "decision": None,
                "action": None,
                "review": None,
                "route": None,
                "communication": None,
                "readback_seen": False,
            }
            self.value["active"] = self.active
            insert(self.session, "start", row["case_id"], copy.deepcopy(self.active))
            return {**row, "scenario": scenario.model_dump(mode="json"), "elapsed_seconds": 0}
        if not self.active:
            raise ValueError("Start a task first")
        scenario = Scenario.model_validate(self.bundle["cases"][self.active["case_id"]])
        case_id = product_case_id(scenario)
        elapsed = (now - datetime.fromisoformat(self.active["started_at"])).total_seconds()
        if elapsed >= 1200 and kind != "finish":
            raise ValueError("20-minute limit reached; save this attempt with Finish")
        self.active["events"].append({"kind": kind, "at": now.isoformat()})
        if kind == "brief":
            if self.active["condition"] != "assisted":
                raise ValueError("Copilot is disabled in manual mode")
            if self.active["decision"] is not None:
                raise ValueError("Primary attempt permits one generated brief")
            self.active["decision"] = (
                await self.call(
                    "POST", f"/api/cases/{case_id}/proposals", {"expected_case_version": 1}
                )
            )["data"]
            return {"decision": self.active["decision"], "actions": self.actions()}
        if kind == "submit":
            if self.active["submitted"] is not None:
                raise ValueError("Decision already submitted")
            if body.get("disposition") not in {"resolve", "escalate"}:
                raise ValueError("Choose resolve or escalate")
            if len(body.get("reason", "")) < 3 or len(body.get("communication", "")) < 3:
                raise ValueError("Reason and communication required")
            if self.active["condition"] == "manual":
                override = manual_engine.set(ManualEngine(scenario, body))
                try:
                    self.active["decision"] = (
                        await self.call(
                            "POST", f"/api/cases/{case_id}/proposals", {"expected_case_version": 1}
                        )
                    )["data"]
                finally:
                    manual_engine.reset(override)
            elif self.active["decision"] is None:
                raise ValueError("Generate and inspect the Copilot brief first")
            if body["disposition"] == "resolve":
                if self.actions() != [
                    {"type": body.get("action_type"), "parameters": body.get("parameters")}
                ]:
                    raise ValueError("Selected parameters differ from persisted proposal")
                self.active["review"] = (
                    await self.call(
                        "POST",
                        f"/api/cases/{case_id}/proposals/1/reviews",
                        {"expected_case_version": 1},
                    )
                )["data"]["review"]
                result = {"status": "awaiting_explicit_approval", "review": self.active["review"]}
            else:
                self.active["route"] = await self.lifecycle(
                    scenario, "escalation_routed", body["reason"], "USR-0002"
                )
                result = {
                    "status": "routed_awaiting_acknowledgement",
                    "route": self.active["route"],
                }
            self.active["submitted"] = {
                key: value for key, value in body.items() if key != "request_id"
            }
            return result
        if kind == "approve":
            review = self.active["review"]
            if not review:
                raise ValueError("Submit a review first")
            await self.call(
                "POST",
                f"/api/reviews/{review['id']}/reserve",
                {"expected_version": 1},
                "administrator",
            )
            await self.call(
                "POST",
                f"/api/reviews/{review['id']}/decisions",
                {
                    "expected_version": 2,
                    "snapshot_fingerprint": review["snapshot_fingerprint"],
                    "decision": "approve",
                    "reason": "Operator explicitly approved the synthetic action.",
                },
                "administrator",
            )
            queue = (await self.call("GET", "/api/actions"))["items"]
            self.active["action"] = next(item for item in queue if item["case_id"] == case_id)
            return {"status": "approved", "action": self.active["action"]}
        if kind in {"execute", "reconcile"}:
            action = self.active["action"]
            if not action:
                raise ValueError("Explicit approval required")
            self.active["action"] = (
                await self.call(
                    "POST",
                    f"/api/actions/{action['id']}/{kind}",
                    {"expected_version": action["version"]},
                )
            )["data"]["action"]
            return cast(dict[str, Any], self.active["action"])
        if kind == "readback":
            action = self.active["action"]
            if not action:
                raise ValueError("No approved action")
            # A receipt alone is not completion. Persist a fresh independent check first.
            self.active["action"] = (
                await self.call(
                    "POST",
                    f"/api/actions/{action['id']}/reconcile",
                    {"expected_version": action["version"]},
                )
            )["data"]["action"]
            result = await self.call("GET", f"/api/actions/{action['id']}")
            target = record(self.session, "target", action["target"])
            self.active["readback_seen"] = True
            return {
                "action": result,
                "independent_synthetic_target": target.value if target else None,
            }
        if kind == "acknowledge":
            if not self.active["route"]:
                raise ValueError("Route an escalation first")
            return await self.lifecycle(
                scenario,
                "escalation_acknowledged",
                "Assigned supervisor accepted the case.",
                self.active["route"]["event_id"],
            )
        if kind == "communicate":
            human = self.active["submitted"]
            if not human:
                raise ValueError("Submit a decision first")
            current = await self.call("GET", f"/api/cases/{case_id}/resolution")
            result = await self.call(
                "POST",
                f"/api/cases/{case_id}/messages",
                {
                    "expected_case_version": current["version"],
                    "channel": "email",
                    "body": human["communication"],
                },
            )
            self.active["communication"] = "STUDY-MESSAGE-" + scenario.case_id
            return {
                "recorded_message": result,
                "reference": self.active["communication"],
                "delivery": "Synthetic operator attestation; no external email sent",
            }
        if kind == "close":
            if not self.active["communication"] or not self.active["readback_seen"]:
                raise ValueError("Inspect read-back and record communication first")
            # Recording the customer message increments case.version. Refresh the proof
            # against that version through the normal API; never relax closure authority.
            await self.command("readback", {})
            return await self.lifecycle(
                scenario,
                "completed",
                "Verified target and recorded synthetic communication.",
                self.active["communication"],
            )
        if kind == "finish":
            observation = None
            error = None
            try:
                if self.active["decision"] is None:
                    raise ValueError("No saved decision")
                with self.db.session() as evidence_session:
                    observation = observe(
                        session=evidence_session,
                        scenario=scenario,
                        decision=self.active["decision"],
                        observed_at=now,
                    )
                human = self.active["submitted"] or {}
                selected, sources = (
                    set(human.get("policy_ids", [])),
                    set(human.get("evidence_ids", [])),
                )
                observation = Observation.model_validate(
                    observation.model_copy(
                        update={
                            "policies": tuple(
                                p for p in observation.policies if p.policy_id in selected
                            ),
                            "facts": {
                                key: fact
                                for key, fact in observation.facts.items()
                                if set(fact.evidence_ids) <= sources
                            },
                            "gaps": tuple(human.get("gaps", [])),
                            "policy_status": human.get("policy_status", "missing"),
                        }
                    ).model_dump()
                )
            except (ValueError, KeyError) as exc:
                error = type(exc).__name__
            self.active.update(
                finished_at=now.isoformat(),
                elapsed_seconds=elapsed,
                timed_out=elapsed >= 1200,
                notes=body.get("notes", ""),
                capture_error=error,
                observation=observation.model_dump(mode="json") if observation else None,
                simulated_followup=[],
            )
            if observation and observation.completion:
                reopened = "reopen" in scenario.tags
                event = None
                if reopened:
                    try:
                        event = await self.lifecycle(
                            scenario,
                            "reopened",
                            "Post-timing simulation: contradictory evidence at virtual day seven.",
                            "SIMULATED-FOLLOWUP-" + scenario.case_id,
                        )
                    except ValueError as exc:
                        self.active["followup_error"] = str(exc)
                self.active["simulated_followup"] = [
                    {
                        "profile": "simulated_time_replay",
                        "days": day,
                        "numerator": int(reopened and event is not None),
                        "denominator": 1,
                        "linked_completion": observation.completion.event_id,
                        "actual_reopen_event": event,
                        "virtual_invalidation_day": 7 if reopened else None,
                        "valid": not reopened or event is not None,
                        "clock_note": "Virtual follow-up; actual event timestamps are preserved.",
                    }
                    for day in (7, 30)
                ]
            insert(self.session, "attempt", scenario.case_id, copy.deepcopy(self.active))
            self.value["index"] += 1
            self.value["active"] = None
            return {
                "saved": scenario.case_id + ".json",
                "elapsed_seconds": elapsed,
                "capture_error": error,
                "status": "recorded_unscored",
            }
        raise ValueError("Unknown study command")


@router.post("/{kind}")
async def command(
    kind: str,
    body: dict[str, Any],
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    packet: str = "practice",
) -> Any:
    db = access(request, actor)
    packet_name(packet)
    try:
        request_id = str(UUID(str(body.get("request_id", ""))))
    except ValueError:
        return JSONResponse({"detail": "A valid request_id UUID is required"}, status_code=422)
    identity = digest({"kind": kind, "body": body, "packet": packet, "actor": actor.actor_id})
    with db.session() as session:
        row = record(session, "session", packet, lock=True)
        bundle = record(session, "packet", packet)
        if row is None or bundle is None:
            return JSONResponse({"detail": "Study has not been initialized"}, status_code=409)
        cached = record(session, "command", request_id)
        if cached:
            if cached.value["identity"] != identity:
                return JSONResponse(
                    {"detail": "Request ID bound to a different command"}, status_code=409
                )
            return JSONResponse(cached.value["response"], status_code=cached.value["status"])
        value = copy.deepcopy(row.value)
        coordinator = Coordinator(request, db, session, value, bundle.value, packet)
        try:
            result, status = await coordinator.command(kind, body), 200
        except (ValueError, KeyError, TypeError, StopIteration) as exc:
            result, status = {"detail": str(exc)[:1000]}, 409
        value["last_command"] = {"request_id": request_id, "status": status, "result": result}
        row.value = value
        insert(
            session,
            "command",
            request_id,
            {"identity": identity, "response": result, "status": status},
        )
        return JSONResponse(result, status_code=status)


@router.get("/evidence/export")
def export(
    request: Request,
    actor: Annotated[ActorContext, Depends(current_actor)],
    packet: str = "practice",
) -> dict[str, Any]:
    db = access(request, actor)
    with db.session() as session:
        bundle = record(session, "packet", packet_name(packet))
        state_row = record(session, "session", packet)
        if bundle is None or state_row is None:
            raise ValueError("Uninitialized study")
        expected = [row["case_id"] for row in bundle.value["order"]]
        return {
            "version": "vercel-study-export-1",
            "packet": packet,
            "session": state_row.value,
            "inputs_sha256": digest(bundle.value),
            "actual_revision": os.environ.get("VERCEL_GIT_COMMIT_SHA", "local-test"),
            "starts": {
                key: row.value for key in expected if (row := record(session, "start", key))
            },
            "attempts": {
                key: row.value for key in expected if (row := record(session, "attempt", key))
            },
        }
