"""Two-stage evaluator: persist observations before loading labels; no product simulator here."""

import re
from collections import Counter
from collections.abc import Callable
from math import sqrt
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.evaluation.case_resolution_v2.corpus import case_path, inputs, manifest
from app.evaluation.case_resolution_v2.models import (
    SCORER_VERSION,
    GoldenLabel,
    Observation,
    RunConfig,
    Scenario,
)
from app.evaluation.case_resolution_v2.scoring import score
from app.evaluation.case_resolution_v2.storage import (
    code_identity,
    digest,
    file_digest,
    read_json,
    write_new,
)


def capture_one(
    *,
    root: Path,
    split: str,
    case_id: str,
    output: Path,
    adapter: Callable[[Scenario], Observation],
    execution_profile: str,
    product_revision: str,
    config: dict[str, Any],
) -> None:
    """Bounded local development utility. Adapter is trusted code with input-only arguments.

    It is not an OS sandbox: Phase 4 must mount inputs without label access in the runtime.
    Holdout capture is deliberately unavailable here.
    """
    if split not in {"development", "regression"}:
        raise ValueError("Local product capture is restricted to development/regression")
    _, cases = inputs(root, split)
    case = next((c for c in cases if c.case_id == case_id), None)
    if case is None:
        raise ValueError("Case not scheduled")
    if output.exists():
        raise FileExistsError(output)
    declare_run(
        root=root,
        split=split,
        output=output,
        case_ids=[case_id],
        execution_profile=execution_profile,
        product_revision=product_revision,
        config=config,
    )
    try:
        observation = adapter(case)
        if not isinstance(observation, Observation):
            raise ValueError("Adapter must return a normalized observation")
        if observation.case_id != case_id or observation.input_sha256 != digest(case):
            raise ValueError("Adapter observation identity mismatch")
        payload: Any = observation.model_dump(mode="json")
    except Exception as exc:
        # Do not persist exception text, which can contain customer content or credentials.
        payload = {
            "capture_error": type(exc).__name__,
            "capture_status": "invalid"
            if isinstance(exc, (ValueError, ValidationError))
            else "provider_failure",
        }
    write_new(output / f"{case_id}.json", payload)


def declare_run(
    *,
    root: Path,
    split: str,
    output: Path,
    case_ids: list[str],
    execution_profile: str,
    product_revision: str,
    config: dict[str, Any],
) -> None:
    """Declare the scheduled population and immutable run identity BEFORE invoking a runtime."""
    spec = manifest(root, split)
    RunConfig.model_validate(config)
    schedule = {"split": split, "case_ids": case_ids}
    known = {e.case_id for e in spec.entries}
    if (
        schedule["split"] != split
        or not case_ids
        or len(case_ids) != len(set(case_ids))
        or not set(case_ids) <= known
    ):
        raise ValueError("Invalid observation schedule")
    if split in {"holdout", "time_study"} and (spec.state != "sealed" or set(case_ids) != known):
        raise ValueError("Sealed evaluation must schedule every primary case exactly once")
    if not re.fullmatch(r"[a-f0-9]{40}", product_revision):
        raise ValueError("Pin an exact product revision")
    if execution_profile not in {
        "evaluator_contract_test",
        "deterministic_product",
        "provider_product",
    }:
        raise ValueError("Unknown execution profile")
    if split in {"holdout", "time_study"} and execution_profile == "evaluator_contract_test":
        raise ValueError("Holdout cannot be used for evaluator debugging")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Run must be declared in an empty directory")
    write_new(output / "schedule.json", schedule)
    write_new(
        output / "run-contract.json",
        dict(
            manifest_sha256=digest(spec),
            schedule_sha256=digest(schedule),
            execution_profile=execution_profile,
            product_revision=product_revision,
            config=config,
            config_sha256=digest(config),
            scorer_version=SCORER_VERSION,
            evaluator_sha256=code_identity(),
        ),
    )


def seal_observations(
    *,
    root: Path,
    split: str,
    output: Path,
    execution_profile: str,
    product_revision: str,
    config: dict[str, Any],
) -> None:
    """Freeze an externally captured run. Missing observations stay scheduled failures."""
    spec = manifest(root, split)
    RunConfig.model_validate(config)
    schedule = read_json(output / "schedule.json")
    case_ids = schedule["case_ids"]
    known = {e.case_id for e in spec.entries}
    if (
        schedule["split"] != split
        or not case_ids
        or len(case_ids) != len(set(case_ids))
        or not set(case_ids) <= known
    ):
        raise ValueError("Invalid observation schedule")
    if split in {"holdout", "time_study"} and (spec.state != "sealed" or set(case_ids) != known):
        raise ValueError("Sealed evaluation must schedule every primary case exactly once")
    if not re.fullmatch(r"[a-f0-9]{40}", product_revision):
        raise ValueError("Pin an exact product revision")
    if execution_profile not in {
        "evaluator_contract_test",
        "deterministic_product",
        "provider_product",
    }:
        raise ValueError("Unknown execution profile")
    if split in {"holdout", "time_study"} and execution_profile == "evaluator_contract_test":
        raise ValueError("Holdout cannot be used for evaluator debugging")
    contract = read_json(output / "run-contract.json")
    expected = dict(
        manifest_sha256=digest(spec),
        schedule_sha256=digest(schedule),
        execution_profile=execution_profile,
        product_revision=product_revision,
        config=config,
        config_sha256=digest(config),
        scorer_version=SCORER_VERSION,
        evaluator_sha256=code_identity(),
    )
    if contract != expected:
        raise ValueError("Run configuration changed after declaration")
    artifacts = {
        case_id: file_digest(output / f"{case_id}.json")
        if (output / f"{case_id}.json").exists()
        else None
        for case_id in case_ids
    }
    write_new(
        output / "observation-seal.json",
        dict(
            manifest_sha256=digest(spec),
            schedule_sha256=digest(schedule),
            artifacts=artifacts,
            run_contract_sha256=digest(contract),
            execution_profile=execution_profile,
            product_revision=product_revision,
            config=config,
            config_sha256=digest(config),
            scorer_version=SCORER_VERSION,
            evaluator_sha256=code_identity(),
        ),
    )


def _rate(n: int, d: int) -> dict[str, Any]:
    interval = None
    if d:
        p = n / d
        z = 1.959963984540054
        center = (p + z * z / (2 * d)) / (1 + z * z / d)
        half = z * sqrt(p * (1 - p) / d + z * z / (4 * d * d)) / (1 + z * z / d)
        interval = [max(0, center - half), min(1, center + half)]
    return {
        "numerator": n,
        "denominator": d,
        "value": n / d if d else None,
        "wilson_95": interval,
        "interval_scope": "synthetic_cases_not_population",
    }


def score_run(*, root: Path, split: str, output: Path) -> dict[str, Any]:
    # A seal must exist before any label is read. Verify all observations first.
    seal = read_json(output / "observation-seal.json")
    schedule = read_json(output / "schedule.json")
    if seal["run_contract_sha256"] != digest(read_json(output / "run-contract.json")):
        raise ValueError("Run declaration changed after observation seal")
    spec, cases = inputs(root, split)
    if (
        seal["manifest_sha256"] != digest(spec)
        or seal["schedule_sha256"] != digest(schedule)
        or seal["config_sha256"] != digest(seal["config"])
    ):
        raise ValueError("Run identity changed after observations were sealed")
    if (
        seal["scorer_version"] != SCORER_VERSION
        or schedule["split"] != split
        or seal["evaluator_sha256"] != code_identity()
    ):
        raise ValueError("Scorer/split identity mismatch")
    raw = {}
    for case_id in schedule["case_ids"]:
        path = output / f"{case_id}.json"
        if (file_digest(path) if path.exists() else None) != seal["artifacts"][case_id]:
            raise ValueError("Observation changed after sealing")
        payload = None
        if path.exists():
            try:
                payload = read_json(path)
                if payload is None:
                    payload = {"invalid_json": "null"}
            except (ValueError, UnicodeError):
                payload = {"invalid_json": "unparseable"}
        raw[case_id] = payload
    by_id = {c.case_id: c for c in cases}
    entries = {e.case_id: e for e in spec.entries}
    grades = []
    eligibility = required_escalation = 0
    invalid = provider_failures = 0
    for case_id, payload in raw.items():
        label = GoldenLabel.model_validate(read_json(case_path(root, split, case_id, "labels")))
        if digest(label) != entries[case_id].label_sha256:
            raise ValueError("Oracle changed after sealing")
        eligibility += label.oracle.automation_eligible
        required_escalation += label.oracle.escalation_required
        observation = None
        status = "missing"
        if payload is not None:
            try:
                observation = Observation.model_validate(payload)
                status = observation.status
            except ValidationError:
                status = (
                    "provider_failure"
                    if isinstance(payload, dict)
                    and payload.get("capture_status") == "provider_failure"
                    else "invalid"
                )
        invalid += status == "invalid"
        provider_failures += status == "provider_failure"
        grade = score(by_id[case_id], label, observation)
        if observation is None:
            grade = grade.model_copy(update={"status": status, "failures": (status,)})
        grades.append(grade)
    count = len(grades)
    confusion = Counter(f"{g.expected_terminal}->{g.observed_terminal or g.status}" for g in grades)
    report = dict(
        scorer_version=SCORER_VERSION,
        run_identity=seal,
        split=split,
        scheduled=count,
        attempted=sum(v is not None for v in raw.values()),
        observed=sum(g.status == "observed" for g in grades),
        scored=count,
        invalid=invalid,
        missing=sum(g.status == "missing" for g in grades),
        provider_failures=provider_failures,
        policy_correctness=_rate(sum(g.policy_correct for g in grades), count),
        correct_completion=_rate(sum(g.correct_completion for g in grades), count),
        safe_automation=_rate(sum(g.automated_resolution for g in grades), count),
        eligible_automation_coverage=_rate(
            sum(g.automated_resolution for g in grades), eligibility
        ),
        actual_escalation=_rate(
            sum(g.correct_completion and g.expected_terminal == "safe_escalation" for g in grades),
            required_escalation,
        ),
        verified_actions={
            "numerator": sum(g.verified_actions for g in grades),
            "denominator": sum(g.action_denominator for g in grades),
        },
        confusion=dict(confusion),
        families=[g.model_dump(mode="json") for g in grades],
        claim_scope=(
            "Evaluator evidence only; product/provider claims require a validated runtime adapter."
        ),
    )
    write_new(output / "report.json", report)
    return report
