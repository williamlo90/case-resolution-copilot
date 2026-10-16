"""Static corpus validation. This module never invokes the product or calculates a score."""

import re
from collections import Counter
from pathlib import Path

from app.evaluation.case_resolution_v2.contracts import SplitManifest, validate_split_isolation
from app.evaluation.case_resolution_v2.models import GoldenLabel, Scenario
from app.evaluation.case_resolution_v2.storage import digest, read_json

ROOT = Path(__file__).resolve().parents[3] / "evaluations" / "case_resolution_v2"


def manifest(root: Path, split: str) -> SplitManifest:
    if split not in {"development", "regression", "holdout", "time_study"}:
        raise ValueError("Unknown split")
    result = SplitManifest.model_validate(read_json(root / f"{split}.manifest.v1.json"))
    if result.split != split:
        raise ValueError("Manifest split mismatch")
    return result


def case_path(root: Path, split: str, case_id: str, kind: str) -> Path:
    if not re.fullmatch(r"[A-Z0-9-]+", case_id) or kind not in {"inputs", "labels"}:
        raise ValueError("Unsafe corpus identifier")
    return root / split / kind / f"{case_id}.json"


def inputs(root: Path, split: str) -> tuple[SplitManifest, tuple[Scenario, ...]]:
    """Input-only loader: do not import/read GoldenLabel files on the execution path."""
    spec = manifest(root, split)
    cases = []
    for entry in spec.entries:
        case = Scenario.model_validate(read_json(case_path(root, split, entry.case_id, "inputs")))
        if digest(case) != entry.input_sha256 or (
            case.case_id,
            case.family_id,
            case.sop_family_id,
        ) != (entry.case_id, entry.family_id, entry.sop_family_id):
            raise ValueError("Input identity/hash mismatch")
        cases.append(case)
    return spec, tuple(cases)


def validate_corpus(root: Path = ROOT) -> dict[str, int]:
    manifests = tuple(
        manifest(root, split) for split in ("development", "regression", "holdout", "time_study")
    )
    validate_split_isolation(manifests)
    counts: dict[str, int] = {}
    semantic_owners: dict[str, str] = {}
    for spec in manifests:
        _, cases = inputs(root, spec.split)
        counts[spec.split] = len(cases)
        for entry, case in zip(spec.entries, cases, strict=True):
            # IDs and numerical variations cannot turn one business rule into a new family.
            rule_text = " ".join(p.get("text", "") for p in case.policies)
            signature = re.sub(r"\d+", "#", re.sub(r"\s+", " ", rule_text.casefold())).strip()
            if signature in semantic_owners and semantic_owners[signature] != case.family_id:
                raise ValueError("Equivalent policy text assigned to different families")
            semantic_owners[signature] = case.family_id
            label = GoldenLabel.model_validate(
                read_json(case_path(root, spec.split, entry.case_id, "labels"))
            )
            oracle = label.oracle
            if digest(label) != entry.label_sha256 or (
                oracle.case_id,
                oracle.family_id,
                oracle.sop_family_id,
                oracle.domain,
            ) != (case.case_id, case.family_id, case.sop_family_id, case.domain):
                raise ValueError("Label identity/hash mismatch")
            if set(oracle.required_facts) != set(label.fact_values) or set(
                label.fact_sources
            ) != set(label.fact_values):
                raise ValueError("Every required fact needs a value and source")
            if set(oracle.resolution_predicates) != set(label.semantic_assertions):
                raise ValueError("Every resolution predicate needs an expected value")
            evidence = {e.id: e for e in case.evidence}
            if not set(oracle.evidence_ids) <= set(evidence):
                raise ValueError("Oracle references absent evidence")
            for policy in oracle.policies:
                if not any(
                    source.get("policy_id") == policy.policy_id
                    and source.get("version") == str(policy.version)
                    and source.get("clause_id") == policy.clause_id
                    for source in case.policies
                ):
                    raise ValueError("Oracle policy is absent from the source rules")
            for key, value in label.fact_values.items():
                if not label.fact_sources[key] or any(
                    source not in evidence or evidence[source].facts.get(key) != value
                    for source in label.fact_sources[key]
                ):
                    raise ValueError("Oracle fact is not grounded in input")
            if (
                case.as_of.utcoffset() is None
                or case.deadline.utcoffset() is None
                or case.deadline <= case.as_of
            ):
                raise ValueError("Invalid scenario deadline")
        if (
            spec.state == "sealed"
            and digest(read_json(root / "suite-config.v1.json")) != spec.config_sha256
        ):
            raise ValueError("Frozen config hash mismatch")
        if spec.split == "development" and len(cases) < 24:
            raise ValueError("Development needs at least 24 distinct families")
        if spec.split == "holdout":
            if Counter(c.domain for c in cases) != {
                "billing": 14,
                "refund": 13,
                "account_recovery": 13,
            }:
                raise ValueError("Holdout domain allocation mismatch")
            for tag in (
                "policy_ambiguity",
                "missing_evidence",
                "conflicting_evidence",
                "unauthorized_actor",
                "expired_authority",
                "stale_sop",
                "duplicate_action",
                "downstream_timeout",
                "reopen",
            ):
                if sum(tag in c.tags for c in cases) < 4:
                    raise ValueError(f"Holdout coverage missing: {tag}")
            if sum(c.critical for c in cases) < 12:
                raise ValueError("Insufficient critical cases")
    return counts
