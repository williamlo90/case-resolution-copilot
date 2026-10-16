"""Create the exposed Phase 4 development revision without reading the old holdout.

The five destination values below are authored source facts. They are not inferred from
product output or from a previously hidden oracle. Run once into an empty revision root.
"""

from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.analysis.deterministic_decision_engine import (
    DECISION_MODEL_VERSION,
    DECISION_PROMPT_VERSION,
)
from app.domain.controlled_operations import OPERATIONS
from app.evaluation.case_resolution_v2.models import SCORER_VERSION, GoldenLabel, Scenario
from app.evaluation.case_resolution_v2.storage import code_identity, digest

SOURCE = Path(__file__).resolve().parents[1] / "evaluations" / "case_resolution_v2"
DESTINATION = Path(__file__).resolve().parents[1] / "evaluations" / "case_resolution_v2_phase4"
AUTHORING_REVISION = "2f0894221c5160500fac1cb9b265947f69cb30bc"
DESTINATION_VALUES: dict[str, dict[str, str]] = {
    "V2-DEV-001": {"new_address": "42 Synthetic Lane, Test City"},
    "V2-DEV-006": {"locale": "id-ID"},
    "V2-DEV-008": {"purchase_order": "PO-SYNTHETIC-008"},
    "V2-DEV-017": {"new_name": "Synthetic Account Seventeen"},
    "V2-DEV-024": {
        "new_email": "owner24@example.test",
        "challenge_destination": "owner24@example.test",
    },
}
OPERATION_REQUESTS = {
    "correct_billing_address": (
        "Correct the invoice mailing address after address validation, "
        "preserving the legal payer."
    ),
    "change_draft_currency": (
        "Change the draft invoice currency before posting with the approved fixed USD amount."
    ),
    "regenerate_invoice_locale": (
        "Regenerate the localized invoice after verifying locale entitlement "
        "without changing the amount."
    ),
    "credit_removed_seats": (
        "Credit seats removed before renewal; check a timed-out credit before another write."
    ),
    "attach_purchase_order": (
        "Attach the purchase order after valid PO authorization; preserve the invoice amount."
    ),
    "refund_course_fee": (
        "Refund the course fee for withdrawal before attendance under a verified policy."
    ),
    "refund_unstarted_premium": (
        "Refund the insurance premium before coverage starts and reconcile a timeout read-only."
    ),
    "rename_account": (
        "Rename the account after verified naming entitlement while retaining "
        "the same immutable owner."
    ),
    "revoke_compromised_sessions": (
        "Revoke compromised sessions once; repeated requests reference "
        "the same revocation operation."
    ),
    "change_recovery_email": (
        "Change the recovery email after a passed challenge and reopen "
        "if that challenge is invalidated."
    ),
}
BLOCKED_REQUESTS = {
    "V2-DEV-003": "Restore suspended service after payment; settlement records conflict.",
    "V2-DEV-004": "Reverse the trial conversion charge because no trial notice was sent.",
    "V2-DEV-005": "Update the dunning contact after verification with supervisor authority.",
    "V2-DEV-009": "Refund an event ticket because the event was postponed over thirty days.",
    "V2-DEV-010": "Refund the warranty repair charge after documented repair failure.",
    "V2-DEV-011": "Refund the storage fee after confirmed custody loss and incident review.",
    "V2-DEV-013": "Return the rental deposit after a clear inspection, but reports disagree.",
    "V2-DEV-014": "Return the shipping upgrade fee because promised service was not delivered.",
    "V2-DEV-015": "Refund the unused app activation after verifying zero activations.",
    "V2-DEV-018": "Issue a password reset token to the verified original account owner.",
    "V2-DEV-019": "Rotate the API key within its existing scope after owner approval.",
    "V2-DEV-021": "Lift the login throttle after abuse clearance and the required report.",
    "V2-DEV-022": "Transfer workspace ownership after resolving conflicting consent records.",
    "V2-DEV-023": (
        "Relink OAuth identity after verifying provider identity and supervisor approval."
    ),
}


def _save(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if path.exists() else "x"
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def _revise(case: dict[str, Any], label: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    case, label = deepcopy(case), deepcopy(label)
    case["tenant_id"] = "ORG-0001"
    for expected_action in label["oracle"]["expected_actions"]:
        expected_action["tenant_id"] = case["tenant_id"]
    case["as_of"] = "2026-10-14T00:00:00Z"
    case["deadline"] = "2026-10-15T00:00:00Z"
    for policy in label["oracle"]["policies"]:
        if policy["date_basis"] == "execution":
            policy["applicable_at"] = "2026-10-14T00:00:01Z"
    for source in case["policies"]:
        clause_id = (
            "POLC-"
            + sha256(f"{source['policy_id']}|{source['version']}|1".encode())
            .hexdigest()[:16]
            .upper()
        )
        old_clause = source["clause_id"]
        source["clause_id"] = clause_id
        for policy in label["oracle"]["policies"]:
            if policy["policy_id"] == source["policy_id"] and policy["clause_id"] == old_clause:
                policy["clause_id"] = clause_id
    actions = label["oracle"]["expected_actions"]
    if not actions:
        if case["case_id"] == "V2-DEV-010":
            # The overlapping second publication is rejected into conflict review.
            # Neither version is bound as applicable evidence for this case.
            label["oracle"]["policies"] = []
        if case["case_id"] in BLOCKED_REQUESTS:
            case["request"] = BLOCKED_REQUESTS[case["case_id"]]
        return case, label
    if len(actions) != 1:
        raise ValueError(f"Unexpected action count: {case['case_id']}")
    action = actions[0]
    operation = action["action_type"]
    if operation not in OPERATIONS:
        return case, label
    spec = OPERATIONS[operation]
    facts = case["evidence"][0]["facts"]
    case["request"] = OPERATION_REQUESTS[operation] + " Target " + facts["requested_target"] + "."
    facts["requested_operation"] = operation
    additions = DESTINATION_VALUES.get(case["case_id"], {})
    for key, value in additions.items():
        source_key = key if key == "challenge_destination" else f"requested_{key}"
        facts[source_key] = value
        label["fact_values"][source_key] = value
        label["fact_sources"][source_key] = [case["evidence"][0]["id"]]
        label["oracle"]["required_facts"].append(source_key)
        if key != "challenge_destination":
            action["consequential_parameters"][key] = value
    facts["target_owner"] = facts["original_recipient"]
    if operation == "change_draft_currency":
        facts["target_current_currency"] = "EUR"
    if operation == "revoke_compromised_sessions":
        facts["target_active_sessions"] = "3"
    if operation == "change_recovery_email":
        facts["target_current_recovery_email"] = "old24@example.test"
    if operation == "rename_account":
        facts["target_current_name"] = "Previous Name"
    if operation == "correct_billing_address":
        facts["target_current_address"] = "Original Address"
    for key in ("requested_operation", *(key for key in facts if key.startswith("target_"))):
        if key not in label["fact_values"]:
            label["fact_values"][key] = facts[key]
            label["fact_sources"][key] = [case["evidence"][0]["id"]]
            label["oracle"]["required_facts"].append(key)
    if spec.scope:
        assert action["consequential_parameters"]["access_scope"] == spec.scope
    else:
        assert action["consequential_parameters"]["currency"] == facts["authorized_currency"]
    rule = {
        "kind": "controlled_operation",
        "action_type": operation,
        "max_amount_minor": int(facts.get("authorized_amount_minor", "0")),
        "currency": facts.get("authorized_currency", "USD"),
    }
    case["policies"][0]["text"] += (
        "\n\n```case-resolution-rules\n"
        + json.dumps({"schema_version": 1, "rules": [rule]})
        + "\n```"
    )
    return case, label


def build() -> None:
    holdout = DESTINATION / "holdout.manifest.v1.json"
    if holdout.exists() and json.loads(holdout.read_text(encoding="utf-8"))["state"] != "planned":
        raise FileExistsError("Holdout is sealed; never overwrite this revision")
    config = {
        "version": "case-resolution-v2-phase4-suite-config-2",
        "source_corpus": "case_resolution_v2",
        "source_development_manifest_sha256": digest(
            json.loads((SOURCE / "development.manifest.v1.json").read_text(encoding="utf-8"))
        ),
        "source_regression_manifest_sha256": digest(
            json.loads((SOURCE / "regression.manifest.v1.json").read_text(encoding="utf-8"))
        ),
        "model_version": DECISION_MODEL_VERSION,
        "prompt_version": DECISION_PROMPT_VERSION,
        "scorer_version": SCORER_VERSION,
        "evaluator_sha256": code_identity(),
        "provider_calls": 0,
        "holdout_families": 40,
        "holdout_allocation": {"billing": 14, "refund": 13, "account_recovery": 13},
        "policy_correctness_floor": 0.95,
        "correct_completion_floor": 0.90,
        "critical_failures_allowed": 0,
    }
    config_hash = digest(config)
    for split in ("development", "regression"):
        source_manifest = json.loads(
            (SOURCE / f"{split}.manifest.v1.json").read_text(encoding="utf-8")
        )
        entries = []
        for item in source_manifest["entries"]:
            name = item["case_id"] + ".json"
            case = json.loads((SOURCE / split / "inputs" / name).read_text(encoding="utf-8"))
            label = json.loads((SOURCE / split / "labels" / name).read_text(encoding="utf-8"))
            case, label = _revise(case, label)
            case = Scenario.model_validate(case).model_dump(mode="json")
            label = GoldenLabel.model_validate(label).model_dump(mode="json")
            _save(DESTINATION / split / "inputs" / name, case)
            _save(DESTINATION / split / "labels" / name, label)
            entries.append(
                {
                    "case_id": item["case_id"],
                    "family_id": item["family_id"],
                    "sop_family_id": item["sop_family_id"],
                    "input_sha256": digest(case),
                    "label_sha256": digest(label),
                }
            )
        source_manifest.update(
            product_revision=AUTHORING_REVISION,
            config_sha256=config_hash,
            model_version=DECISION_MODEL_VERSION,
            prompt_version=DECISION_PROMPT_VERSION,
            scorer_version=SCORER_VERSION,
            entries=entries,
        )
        _save(DESTINATION / f"{split}.manifest.v1.json", source_manifest)
    _save(DESTINATION / "suite-config.v1.json", config)
    _save(
        DESTINATION / "holdout.manifest.v1.json",
        {
            "version": "case-resolution-v2-manifest-1",
            "split": "holdout",
            "state": "planned",
            "seed": 20261015,
            "sealed_at": None,
            "product_revision": None,
            "config_sha256": None,
            "model_version": None,
            "prompt_version": None,
            "scorer_version": None,
            "entries": [],
        },
    )
    _save(
        DESTINATION / "time_study.manifest.v1.json",
        json.loads((SOURCE / "time_study.manifest.v1.json").read_text(encoding="utf-8")),
    )


if __name__ == "__main__":
    build()
