"""Exposed SOP regression replay; not a holdout or end-to-end completion benchmark."""

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.analysis.deterministic_decision_engine import (
    DeterministicDecisionEngine,
    combined_context_fingerprint,
    combined_evidence_fingerprint,
    decision_input_fingerprint,
)
from app.analysis.sop_rules import validate_rule_scope
from app.domain.cases import CaseWorkspaceRecord
from app.domain.decision_briefs import DecisionAnalysis
from app.domain.policies import (
    EvidenceRetrievalResult,
    EvidenceRetrievalStatus,
    PolicyEvidenceBundle,
)

ROOT = Path(__file__).resolve().parents[2] / "evaluations" / "sop_revisions"


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: str
    version: int
    effective_from: AwareDatetime
    effective_to: AwareDatetime | None
    publisher: str
    publisher_role: str
    source: str
    sha256: str
    rollback_of: int | None
    restores_content_of: int | None
    category: str


class ReplayCase(BaseModel):
    id: str
    family: str
    workspace: CaseWorkspaceRecord
    evidence_template: PolicyEvidenceBundle


class ReplayInputs(BaseModel):
    policies: list[Revision]
    cases: list[ReplayCase]
    dates: list[AwareDatetime]


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def load_inputs() -> ReplayInputs:
    manifest = json.loads((ROOT / "manifest.json").read_text())
    raw = (ROOT / "inputs.json").read_text()
    if sha(raw) != manifest["files"]["inputs.json"]:
        raise ValueError("Replay inputs changed after freeze")
    data = ReplayInputs.model_validate_json(raw)
    for revision in data.policies:
        if revision.sha256 != sha(revision.source) or revision.publisher_role != "administrator":
            raise ValueError("Invalid replay source identity or publisher")
        validate_rule_scope(revision.source, [revision.category])
    return data


def retrieve(data: ReplayInputs, case: ReplayCase, at: datetime) -> Revision:
    matches = [
        p
        for p in data.policies
        if p.family == case.family
        and p.effective_from <= at
        and (p.effective_to is None or at < p.effective_to)
    ]
    if len(matches) != 1:
        raise ValueError("Replay authority missing or ambiguous")
    return matches[0]


def observe(case: ReplayCase, revision: Revision, at: datetime) -> dict[str, object]:
    bundle = case.evidence_template.model_copy(deep=True)
    source_hash = revision.sha256
    policy_id = uuid5(NAMESPACE_URL, f"sop-replay:{revision.family}")
    version_id = uuid5(policy_id, str(revision.version))
    clause_id = uuid5(version_id, "rules")
    bundle.policy.id = policy_id
    bundle.policy.organization_id = case.workspace.case.organization_id
    bundle.policy.public_id = f"POL-REPLAY-{revision.family.upper()}"
    bundle.policy.current_version = revision.version
    bundle.policy.title = f"{revision.family} SOP revision"
    bundle.version.id = version_id
    bundle.version.policy_id = policy_id
    bundle.version.public_id = f"POLV-REPLAY-{revision.family.upper()}-{revision.version}"
    bundle.version.version = revision.version
    bundle.version.organization_id = case.workspace.case.organization_id
    bundle.version.source_text = revision.source
    bundle.version.content_hash = source_hash
    bundle.version.case_categories = [revision.category]
    bundle.version.effective_from = revision.effective_from
    bundle.version.effective_to = revision.effective_to
    bundle.version.created_by = revision.publisher
    bundle.clause.id = clause_id
    bundle.clause.public_id = f"POLC-REPLAY-{revision.family.upper()}-{revision.version}"
    bundle.clause.policy_id = policy_id
    bundle.clause.policy_version_id = version_id
    bundle.clause.organization_id = case.workspace.case.organization_id
    bundle.clause.text = revision.source
    bundle.clause.content_hash = source_hash
    bundle.evidence.id = uuid5(version_id, case.id)
    bundle.evidence.organization_id = case.workspace.case.organization_id
    bundle.evidence.case_id = case.workspace.case.id
    bundle.evidence.policy_id = policy_id
    bundle.evidence.policy_version_id = version_id
    bundle.evidence.clause_id = clause_id
    bundle.evidence.fingerprint = sha(f"{case.id}:{version_id}:{source_hash}:{at.isoformat()}")
    bundle.evidence.policy_content_hash = source_hash
    bundle.evidence.clause_content_hash = source_hash
    bundle.evidence.excerpt = revision.source
    bundle.evidence.recorded_at = at
    bundle.evidence.effective_from = revision.effective_from
    bundle.evidence.effective_to = revision.effective_to
    evidence = EvidenceRetrievalResult(
        status=EvidenceRetrievalStatus.RELEVANT,
        reason="Frozen SOP timeline retrieval",
        evidence=[bundle],
    )
    engine = DeterministicDecisionEngine()
    fingerprint = decision_input_fingerprint(
        workspace=case.workspace,
        evidence=evidence,
        context_fingerprint=combined_context_fingerprint(case.workspace),
        evidence_fingerprint=combined_evidence_fingerprint(evidence),
        model_version=engine.model_version,
        prompt_version=engine.prompt_version,
        graph_version=engine.graph_version,
        risk_rule_version=engine.risk_rule_version,
    )
    analysis = engine.analyze(
        workspace=case.workspace, evidence=evidence, input_fingerprint=fingerprint
    )
    return {
        "case_id": case.id,
        "revision": revision.version,
        "family": revision.family,
        "as_of": at.isoformat(),
        "source_sha256": source_hash,
        "source_version": bundle.version.public_id,
        "input_fingerprint": fingerprint,
        "analysis": analysis.model_dump(mode="json"),
    }


def run(output: Path) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Full replay is restricted to isolated GitHub Actions")
    output.mkdir(parents=True, exist_ok=False)
    data = load_inputs()
    engine = DeterministicDecisionEngine()
    config = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "model": engine.model_version,
        "prompt": engine.prompt_version,
        "graph": engine.graph_version,
        "rules": engine.risk_rule_version,
        "run_date": datetime.now(UTC).isoformat(),
        "provider_calls": 0,
        "fixture_manifest": json.loads((ROOT / "manifest.json").read_text()),
        "environment": "isolated-github-actions",
        "seed": 20261014,
    }
    (output / "config.json").write_text(json.dumps(config, indent=2))
    observations = []
    for at in data.dates:
        for case in data.cases:
            revision = retrieve(data, case, at)
            try:
                observed = observe(case, revision, at)
                # Pure deterministic engine replay, including checkpoint and response controls.
                observed["deterministic"] = observed == observe(case, revision, at)
            except Exception as exc:
                observed = {
                    "case_id": case.id,
                    "revision": revision.version,
                    "family": case.family,
                    "as_of": at.isoformat(),
                    "error": type(exc).__name__,
                    "deterministic": False,
                }
            observations.append(observed)
    raw_observations = json.dumps(observations, indent=2)
    (output / "observations.json").write_text(raw_observations)
    # Labels are opened only after observations have been durably written.
    raw_labels = (ROOT / "labels.json").read_text()
    if sha(raw_labels) != config["fixture_manifest"]["files"]["labels.json"]:
        raise ValueError("Replay oracle changed after freeze")
    labels = json.loads(raw_labels)["labels"]
    counts: dict[str, dict[str, int]] = {}
    traces = []
    for observed in observations:
        key = f"{observed['case_id']}:{observed['revision']}"
        label = labels[key]
        analysis = (
            DecisionAnalysis.model_validate(observed["analysis"])
            if "analysis" in observed
            else None
        )
        action_types = [a.type for a in analysis.proposed_actions] if analysis else []
        expected_action = label["action"] if label["allowed"] else "request_information"
        correct = (
            action_types == [expected_action]
            and (analysis is not None and analysis.state.value == "ready_for_review")
            == label["allowed"]
            and bool(observed["deterministic"])
        )
        if analysis and len(analysis.proposed_actions) == 1:
            action = analysis.proposed_actions[0]
            expected_amount = Decimal(label["impact_amount"]) if label["impact_amount"] else None
            correct = correct and (
                action.parameters == label["parameters"]
                and action.impact_amount == expected_amount
                and action.impact_currency == label["impact_currency"]
                and action.review_required == label["review_required"]
                and analysis.policy_status is EvidenceRetrievalStatus.RELEVANT
                and (
                    not label["required_gap"]
                    or any(
                        label["required_gap"] in gap.description and gap.blocking
                        for gap in analysis.missing_information
                    )
                )
            )
        group = f"{observed['family']}:v{observed['revision']}"
        count = counts.setdefault(group, {"correct": 0, "eligible": 0})
        count["eligible"] += 1
        count["correct"] += int(correct)
        traces.append(
            {
                "key": key,
                "correct": correct,
                "expected": label,
                "actual_actions": action_types,
                "error": observed.get("error"),
            }
        )
    report = {
        "scope": "exposed synthetic SOP decision regression; no completion/holdout claim",
        "config": config,
        "observation_sha256": sha(raw_observations),
        "per_revision": counts,
        "correct": sum(c["correct"] for c in counts.values()),
        "eligible": len(observations),
        "traces": traces,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2))
    if report["correct"] != report["eligible"]:
        raise RuntimeError("SOP replay failed; see preserved observation and error traces")
