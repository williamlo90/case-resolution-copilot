"""Validate Phase 0 design artifacts without executing product or reading holdout labels."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from app.evaluation.case_resolution_v2.contracts import (
    MeasurementContract,
    OracleLabel,
    PairedOutcome,
    RateObservation,
    SplitManifest,
    validate_split_isolation,
)

ROOT = Path(__file__).resolve().parents[1] / "evaluations" / "case_resolution_v2"
SCHEMAS: dict[str, type[BaseModel]] = {
    "measurement-contract.schema.json": MeasurementContract,
    "manifest.schema.json": SplitManifest,
    "oracle.schema.json": OracleLabel,
    "rate.schema.json": RateObservation,
    "paired-outcome.schema.json": PairedOutcome,
}
METRIC_NAMES = {
    "policy_correctness",
    "correct_completion",
    "safe_automation",
    "eligible_automation_coverage",
    "actual_escalation",
    "missed_escalation",
    "unexpected_escalation",
    "verified_action",
    "false_closure",
    "unsafe_effect",
    "missing_observation",
    "reopen_7d",
    "reopen_30d",
    "reopen_correctness",
    "provider_cost_per_verified_resolution",
    "total_cost_per_verified_resolution",
}


def validate_design(root: Path = ROOT) -> MeasurementContract:
    # Git may convert LF/CRLF on checkout; line endings are not a contract change.
    contract_bytes = (root / "measurement-contract.v1.json").read_bytes().replace(b"\r\n", b"\n")
    expected_digest = (root / "measurement-contract.v1.sha256").read_text().strip()
    if sha256(contract_bytes).hexdigest() != expected_digest:
        raise ValueError("Frozen measurement contract hash mismatch")
    contract = MeasurementContract.model_validate_json(contract_bytes)
    if set(contract.metrics) != METRIC_NAMES:
        raise ValueError("Missing or unexpected metric definitions")
    manifests_list: list[SplitManifest] = []
    for split in ("development", "regression", "holdout", "time_study"):
        manifest = SplitManifest.model_validate_json(
            (root / f"{split}.manifest.v1.json").read_text(encoding="utf-8")
        )
        if manifest.split != split:
            raise ValueError("Manifest split does not match its file")
        manifests_list.append(manifest)
    manifests = tuple(manifests_list)
    validate_split_isolation(manifests)
    for name, model in SCHEMAS.items():
        if json.loads((root / name).read_text(encoding="utf-8")) != model.model_json_schema():
            raise ValueError(f"Schema drift: {name}")
    return contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-schemas", action="store_true")
    args = parser.parse_args()
    if args.export_schemas:
        for name, model in SCHEMAS.items():
            (ROOT / name).write_text(
                json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
            )
    validate_design()
    print("PASS: V2 design contracts and schema exports. No product evaluation executed.")


if __name__ == "__main__":
    main()
