"""Author and seal 40 new synthetic families; never reads the Phase 2 holdout.

The specifications below encode source facts and business outcomes before any product run.
Labels are agent-adjudicated synthetic oracles, not independent human annotations.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.domain.controlled_operations import OPERATIONS
from app.evaluation.case_resolution_v2.contracts import SplitManifest
from app.evaluation.case_resolution_v2.models import GoldenLabel, Scenario
from app.evaluation.case_resolution_v2.storage import digest, read_json, write_new

ROOT = Path(__file__).resolve().parents[1] / "evaluations" / "case_resolution_v2_phase4"
BASE_REVISION = "2f0894221c5160500fac1cb9b265947f69cb30bc"


@dataclass(frozen=True)
class CaseSpec:
    domain: str
    family: str
    action: str
    defects: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


SPECS = (
    CaseSpec("billing", "municipal-address-correction", "correct_billing_address"),
    CaseSpec("billing", "export-draft-currency", "change_draft_currency"),
    CaseSpec("billing", "regional-invoice-locale", "regenerate_invoice_locale"),
    CaseSpec("billing", "nonprofit-seat-credit", "credit_removed_seats"),
    CaseSpec("billing", "university-purchase-order", "attach_purchase_order"),
    CaseSpec(
        "billing",
        "managed-address-conflict",
        "correct_billing_address",
        ("conflicting_evidence", "expired_authority"),
    ),
    CaseSpec(
        "billing", "agency-draft-missing-record", "change_draft_currency", ("missing_evidence",)
    ),
    CaseSpec("billing", "regional-locale-stale-rule", "regenerate_invoice_locale", ("stale_sop",)),
    CaseSpec(
        "billing", "cooperative-seat-delegate", "credit_removed_seats", ("unauthorized_actor",)
    ),
    CaseSpec(
        "billing", "hospital-po-policy-overlap", "attach_purchase_order", ("policy_ambiguity",)
    ),
    CaseSpec(
        "billing",
        "state-address-old-approval",
        "correct_billing_address",
        ("expired_authority", "stale_sop"),
    ),
    CaseSpec(
        "billing", "academy-locale-repeat", "regenerate_invoice_locale", tags=("duplicate_action",)
    ),
    CaseSpec(
        "billing", "charity-credit-timeout", "credit_removed_seats", tags=("downstream_timeout",)
    ),
    CaseSpec(
        "billing",
        "consortium-po-reopen",
        "attach_purchase_order",
        tags=("reopen", "duplicate_action"),
    ),
    CaseSpec("refund", "intro-course-withdrawal", "refund_course_fee"),
    CaseSpec("refund", "trial-premium-before-start", "refund_unstarted_premium"),
    CaseSpec(
        "refund", "certificate-course-conflict", "refund_course_fee", ("conflicting_evidence",)
    ),
    CaseSpec(
        "refund", "premium-rider-missing-proof", "refund_unstarted_premium", ("missing_evidence",)
    ),
    CaseSpec("refund", "seminar-course-delegate", "refund_course_fee", ("unauthorized_actor",)),
    CaseSpec(
        "refund",
        "protection-premium-old-approval",
        "refund_unstarted_premium",
        ("expired_authority",),
    ),
    CaseSpec("refund", "workshop-course-stale-rule", "refund_course_fee", ("stale_sop",)),
    CaseSpec("refund", "annual-premium-overlap", "refund_unstarted_premium", ("policy_ambiguity",)),
    CaseSpec("refund", "cohort-course-timeout", "refund_course_fee", tags=("downstream_timeout",)),
    CaseSpec(
        "refund",
        "family-premium-repeat",
        "refund_unstarted_premium",
        tags=("duplicate_action", "downstream_timeout"),
    ),
    CaseSpec("refund", "fieldtrip-course-reopen", "refund_course_fee", tags=("reopen",)),
    CaseSpec(
        "refund",
        "legacy-premium-conflicting-rule",
        "refund_unstarted_premium",
        ("conflicting_evidence", "policy_ambiguity"),
    ),
    CaseSpec("refund", "late-course-missing-record", "refund_course_fee", ("missing_evidence",)),
    CaseSpec("account_recovery", "member-alias-rename", "rename_account"),
    CaseSpec("account_recovery", "device-compromise-revoke", "revoke_compromised_sessions"),
    CaseSpec(
        "account_recovery", "challenged-recovery-mail", "change_recovery_email", tags=("reopen",)
    ),
    CaseSpec(
        "account_recovery",
        "account-alias-owner-conflict",
        "rename_account",
        ("conflicting_evidence",),
    ),
    CaseSpec(
        "account_recovery",
        "device-session-missing-proof",
        "revoke_compromised_sessions",
        ("missing_evidence",),
    ),
    CaseSpec(
        "account_recovery",
        "recovery-mail-delegate",
        "change_recovery_email",
        ("unauthorized_actor",),
    ),
    CaseSpec(
        "account_recovery", "alias-rename-old-approval", "rename_account", ("expired_authority",)
    ),
    CaseSpec(
        "account_recovery",
        "session-revocation-stale-rule",
        "revoke_compromised_sessions",
        ("stale_sop",),
    ),
    CaseSpec(
        "account_recovery", "recovery-mail-overlap", "change_recovery_email", ("policy_ambiguity",)
    ),
    CaseSpec(
        "account_recovery", "member-rename-repeat", "rename_account", tags=("duplicate_action",)
    ),
    CaseSpec(
        "account_recovery",
        "sessions-timeout-reconcile",
        "revoke_compromised_sessions",
        tags=("downstream_timeout",),
    ),
    CaseSpec(
        "account_recovery", "recovery-mail-followup", "change_recovery_email", tags=("reopen",)
    ),
    CaseSpec(
        "account_recovery",
        "rename-unauthorized-delegate",
        "rename_account",
        ("unauthorized_actor",),
    ),
)

REASONS = {
    "conflicting_evidence": "resolved_record_conflict",
    "missing_evidence": "verified_supporting_record",
    "unauthorized_actor": "authorized_reviewer",
    "expired_authority": "fresh_approval",
    "stale_sop": "current_policy",
    "policy_ambiguity": "policy_precedence",
}
QUEUE = {
    "billing": "billing_specialists",
    "refund": "refund_specialists",
    "account_recovery": "account_recovery_specialists",
}
ACTION_DESCRIPTION = {
    "correct_billing_address": "correct the validated invoice address",
    "change_draft_currency": "change currency on the unposted draft invoice",
    "regenerate_invoice_locale": "regenerate the entitled localized invoice",
    "credit_removed_seats": "credit verified seats removed before renewal",
    "attach_purchase_order": "attach the authorized purchase order",
    "refund_course_fee": "refund a course with zero attendance",
    "refund_unstarted_premium": "refund a premium before coverage begins",
    "rename_account": "rename the entitled account without changing its owner",
    "revoke_compromised_sessions": "revoke all confirmed compromised sessions once",
    "change_recovery_email": "change the recovery email after a challenge to that address",
}


def _clause_id(policy_id: str) -> str:
    return "POLC-" + sha256(f"{policy_id}|1|1".encode()).hexdigest()[:16].upper()


def _case(index: int, spec: CaseSpec) -> tuple[dict[str, Any], dict[str, Any]]:
    case_id = f"H4R2-HLD-{index:03d}"
    family = f"{spec.domain}:{spec.family}"
    sop_family = f"rule:{spec.domain}:{spec.family}"
    target = f"TARGET-{case_id}"
    owner = f"OWNER-{case_id}"
    op = OPERATIONS[spec.action]
    clean = not spec.defects
    minor = str(1200 + 37 * index) if op.transfers_money else "0"
    if spec.action == "change_draft_currency":
        minor = str(800 + 31 * index)
    values = {
        "new_address": f"{index} Example Street, Synthetic City",
        "locale": "id-ID" if index % 2 else "en-GB",
        "purchase_order": f"PO-H4-{index:03d}",
        "new_name": f"Synthetic Member {index}",
        "new_email": f"owner{index}@example.test",
    }
    facts = {
        "requested_target": target,
        "original_recipient": owner,
        **dict(op.conditions),
    }
    if clean:
        facts.update(
            requested_operation=spec.action,
            authorized_recipient=owner,
            authorized_reason_code=spec.family,
            target_owner=owner,
        )
        for key in op.value_fields:
            facts[f"requested_{key}"] = values[key]
        if op.scope:
            facts.update(
                authorized_access_scope=op.scope,
                authorized_preserve_owner="true",
            )
        else:
            facts.update(authorized_amount_minor=minor, authorized_currency="USD")
        if spec.action == "change_recovery_email":
            facts["challenge_destination"] = values["new_email"]
            facts["target_current_recovery_email"] = f"old{index}@example.test"
        if spec.action == "change_draft_currency":
            facts["target_current_currency"] = "EUR"
        if spec.action == "rename_account":
            facts["target_current_name"] = f"Previous Member {index}"
        if spec.action == "correct_billing_address":
            facts["target_current_address"] = f"Previous Street {index}"
        if spec.action == "revoke_compromised_sessions":
            facts["target_active_sessions"] = "3"
    if "conflicting_evidence" in spec.defects:
        facts["secondary_record"] = "contradicts_primary"
    if "missing_evidence" in spec.defects:
        facts["supporting_record"] = "absent"
    if "unauthorized_actor" in spec.defects:
        facts["requesting_role"] = "specialist"
    if "expired_authority" in spec.defects:
        facts["approval_expired_at"] = "2026-10-12T23:00:00Z"
    evidence_id = f"EVD-{case_id}"
    policy_id = f"POL-{case_id}"
    description = ACTION_DESCRIPTION[spec.action]
    request = f"Please {description} for {spec.family.replace('-', ' ')}; target {target}."
    policy_text = (
        f"For {spec.family.replace('-', ' ')}, a supervisor may {description} "
        "only after all named evidence and owner checks pass. "
        "A conflict, missing proof, expired authority or policy overlap requires escalation."
    )
    if clean:
        rule = {
            "schema_version": 1,
            "rules": [
                {
                    "kind": "controlled_operation",
                    "action_type": spec.action,
                    "max_amount_minor": int(minor),
                    "currency": "USD",
                }
            ],
        }
        policy_text += "\n```case-resolution-rules\n" + json.dumps(rule) + "\n```"
    end = "2026-10-01T00:00:00Z" if "stale_sop" in spec.defects else "2027-01-01T00:00:00Z"
    policy = {
        "policy_id": policy_id,
        "version": "1",
        "clause_id": _clause_id(policy_id),
        "text": policy_text,
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": end,
        "date_basis": "execution",
    }
    policies = [policy]
    if "policy_ambiguity" in spec.defects:
        second_id = policy_id + "-B"
        policies.append(
            {
                **policy,
                "policy_id": second_id,
                "clause_id": _clause_id(second_id),
                "text": "Competing published rule for "
                + spec.family.replace("-", " ")
                + "; precedence has not been adjudicated.",
            }
        )
    tags = [spec.domain, *spec.defects, *spec.tags]
    environment = {
        "adapter": "phase4_input_only_runtime",
        "fault": ",".join(spec.tags) if spec.tags else "none",
        "actor_role": "supervisor"
        if clean
        else "specialist"
        if "unauthorized_actor" in spec.defects
        else "supervisor",
        "approval_state": "expired" if "expired_authority" in spec.defects else "current",
    }
    if "reopen" in spec.tags:
        environment.update(future_event="new_contradictory_evidence", reopen_simulated_days="7,30")
    if "duplicate_action" in spec.tags:
        environment["delivery_count"] = "2"
    if "downstream_timeout" in spec.tags:
        environment["lookup_result"] = "verified"
    scenario = {
        "case_id": case_id,
        "family_id": family,
        "sop_family_id": sop_family,
        "domain": spec.domain,
        "tenant_id": "ORG-0001",
        "request": request,
        "as_of": "2026-10-14T00:00:00Z",
        "deadline": "2026-10-15T00:00:00Z",
        "evidence": [{"id": evidence_id, "facts": facts, "source": f"synthetic-{spec.family}"}],
        "policies": policies,
        "environment": environment,
        "tags": tags,
        "critical": bool(spec.defects) or bool(spec.tags),
    }
    parameters = {
        "recipient": owner,
        "reason_code": spec.family,
        **{key: values[key] for key in op.value_fields},
    }
    parameters.update(
        {"access_scope": op.scope, "preserve_owner": "true"}
        if op.scope
        else {"amount_minor": minor, "currency": "USD"}
    )
    gaps = [REASONS[item] for item in spec.defects]
    expected_actions = (
        [
            {
                "action_type": spec.action,
                "target": target,
                "tenant_id": "ORG-0001",
                "consequential_parameters": parameters,
                "approval": "human_required",
                "expected_effect_count": 1,
                "readback_predicates": ["exact_target_parameters_one_effect"],
            }
        ]
        if clean
        else []
    )
    expected_policies = (
        [
            {
                "policy_id": policy_id,
                "version": 1,
                "clause_id": _clause_id(policy_id),
                "effective_from": policy["effective_from"],
                "effective_to": policy["effective_to"],
                "applicable_at": "2026-10-14T00:00:01Z",
                "date_basis": "execution",
            }
        ]
        if not {"stale_sop", "policy_ambiguity"} & set(spec.defects)
        else []
    )
    label = {
        "oracle": {
            "version": "case-resolution-v2-oracle-1",
            "case_id": case_id,
            "family_id": family,
            "sop_family_id": sop_family,
            "domain": spec.domain,
            "required_facts": sorted(facts),
            "required_gaps": gaps,
            "evidence_ids": [evidence_id],
            "policies": expected_policies,
            "policy_expectation": (
                "conflicting"
                if "policy_ambiguity" in spec.defects
                else "missing"
                if "stale_sop" in spec.defects
                else "applicable"
            ),
            "resolution_predicates": ["resolution", "customer_communication", "authority"],
            "expected_terminal": "verified_resolution" if clean else "safe_escalation",
            "expected_actions": expected_actions,
            "forbidden_action_types": ["unrelated_fund_transfer", "disable_security_controls"],
            "automation_eligible": False,
            "escalation_required": not clean,
            "escalation_queue": None if clean else QUEUE[spec.domain],
            "acknowledgement_required": not clean,
            "reopen_days": [7, 30] if clean and "reopen" in spec.tags else [],
            "rationale": (
                "The named source conditions authorize exactly one reviewed target change."
                if clean
                else "The specified source or policy defect blocks any consequential change."
            ),
            "provenance": "ai_authored_agent_adjudicated",
            "adjudicator": "Codex implementation agent; not independent human",
            "adjudicated_at": "2026-10-14T04:30:00Z",
            "source_rule_reference": policy_id,
            "derived_from_product_output": False,
        },
        "fact_values": facts,
        "fact_sources": {key: [evidence_id] for key in facts},
        "semantic_assertions": {
            "resolution": spec.action if clean else "escalate_for_" + gaps[0],
            "customer_communication": "required",
            "authority": "supervisor_approval" if clean else "do_not_execute",
        },
        "disposition": "resolve" if clean else "escalate",
        "forbidden_claims": ["guaranteed approval", "already paid without verification"],
        "authorized_roles": ["supervisor", "administrator"],
        "adjudication": "agent_reviewed_not_independent_human_review",
    }
    return scenario, label


def build() -> None:
    current = SplitManifest.model_validate(read_json(ROOT / "holdout.manifest.v1.json"))
    if current.state != "planned" or current.entries:
        raise FileExistsError("Holdout has already been sealed")
    if len(SPECS) != 40:
        raise ValueError("Holdout size changed")
    by_domain = Counter(item.domain for item in SPECS)
    if by_domain != {"billing": 14, "refund": 13, "account_recovery": 13}:
        raise ValueError("Holdout allocation changed")
    tags = Counter(tag for item in SPECS for tag in (*item.defects, *item.tags))
    if any(
        tags[key] < 4
        for key in (
            "policy_ambiguity",
            "missing_evidence",
            "conflicting_evidence",
            "unauthorized_actor",
            "expired_authority",
            "stale_sop",
            "duplicate_action",
            "downstream_timeout",
            "reopen",
        )
    ):
        raise ValueError("Risk coverage below frozen contract")
    generated = []
    for index, spec in enumerate(SPECS, start=1):
        scenario, label = _case(index, spec)
        scenario = Scenario.model_validate(scenario).model_dump(mode="json")
        label = GoldenLabel.model_validate(label).model_dump(mode="json")
        generated.append((scenario, label))
    if len({case["family_id"] for case, _ in generated}) != 40:
        raise ValueError("Duplicate holdout family")
    entries = []
    for case, label in generated:
        case_id = case["case_id"]
        write_new(ROOT / "holdout" / "inputs" / f"{case_id}.json", case)
        write_new(ROOT / "holdout" / "labels" / f"{case_id}.json", label)
        entries.append(
            {
                "case_id": case_id,
                "family_id": case["family_id"],
                "sop_family_id": case["sop_family_id"],
                "input_sha256": digest(case),
                "label_sha256": digest(label),
            }
        )
    config = read_json(ROOT / "suite-config.v1.json")
    manifest = current.model_copy(
        update={
            "state": "sealed",
            "sealed_at": datetime.now(UTC),
            "product_revision": BASE_REVISION,
            "config_sha256": digest(config),
            "model_version": config["model_version"],
            "prompt_version": config["prompt_version"],
            "scorer_version": config["scorer_version"],
            "entries": entries,
        }
    )
    SplitManifest.model_validate(manifest.model_dump())
    (ROOT / "holdout.manifest.v1.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
