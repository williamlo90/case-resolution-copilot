"""Explicit operation contracts for reviewed billing, refund and identity changes."""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.domain.cases import CaseWorkspaceRecord
from app.domain.decision_briefs import ProposedActionDraft

OperationType = Literal[
    "correct_billing_address",
    "change_draft_currency",
    "regenerate_invoice_locale",
    "credit_removed_seats",
    "attach_purchase_order",
    "refund_course_fee",
    "refund_unstarted_premium",
    "rename_account",
    "revoke_compromised_sessions",
    "change_recovery_email",
]


@dataclass(frozen=True)
class OperationSpec:
    category: str
    provider: str
    conditions: tuple[tuple[str, str], ...]
    value_fields: tuple[str, ...]
    scope: str | None = None
    transfers_money: bool = False


OPERATIONS: dict[str, OperationSpec] = {
    "correct_billing_address": OperationSpec(
        "billing_dispute", "billing", (("address_validation", "passed"),), ("new_address",)
    ),
    "change_draft_currency": OperationSpec(
        "billing_dispute", "billing", (("invoice_state", "draft"),), ()
    ),
    "regenerate_invoice_locale": OperationSpec(
        "billing_dispute", "billing", (("locale_entitlement", "verified"),), ("locale",)
    ),
    "credit_removed_seats": OperationSpec(
        "billing_dispute", "billing", (("removed_seats", "verified"),), (), transfers_money=True
    ),
    "attach_purchase_order": OperationSpec(
        "billing_dispute", "billing", (("po_authorization", "valid"),), ("purchase_order",)
    ),
    "refund_course_fee": OperationSpec(
        "refund_request", "billing", (("attendance_percent", "0"),), (), transfers_money=True
    ),
    "refund_unstarted_premium": OperationSpec(
        "refund_request", "billing", (("coverage_not_started", "true"),), (), transfers_money=True
    ),
    "rename_account": OperationSpec(
        "account_access",
        "identity",
        (("name_entitlement", "verified"),),
        ("new_name",),
        "same_owner",
    ),
    "revoke_compromised_sessions": OperationSpec(
        "account_access", "identity", (("session_compromise", "confirmed"),), (), "all_sessions"
    ),
    "change_recovery_email": OperationSpec(
        "account_access",
        "identity",
        (("email_challenge", "passed"),),
        ("new_email",),
        "recovery_only",
    ),
}


def field(workspace: CaseWorkspaceRecord, key: str) -> str | None:
    values = {
        str(row.fields[key]).strip() for row in workspace.business_contexts if key in row.fields
    }
    return next(iter(values)) if len(values) == 1 and "" not in values else None


def has_operation_request(workspace: CaseWorkspaceRecord) -> bool:
    return any("requested_operation" in row.fields for row in workspace.business_contexts)


def operation_gaps(workspace: CaseWorkspaceRecord, action_type: str) -> list[str]:
    spec = OPERATIONS.get(action_type)
    if spec is None:
        return ["supported_operation"]
    gaps = []
    if workspace.case.category.value != spec.category:
        gaps.append("matching_operation_category")
    if field(workspace, "requested_operation") != action_type:
        gaps.append("unambiguous_requested_operation")
    gaps.extend(key for key, expected in spec.conditions if field(workspace, key) != expected)
    if field(workspace, "secondary_record") == "contradicts_primary":
        gaps.append("resolved_record_conflict")
    if field(workspace, "supporting_record") == "absent":
        gaps.append("verified_supporting_record")
    required = [
        "requested_target",
        "original_recipient",
        "authorized_recipient",
        "authorized_reason_code",
    ]
    required.extend(f"requested_{key}" for key in spec.value_fields)
    gaps.extend(key for key in required if not field(workspace, key))
    if field(workspace, "original_recipient") != field(workspace, "authorized_recipient"):
        gaps.append("original_recipient_match")
    if spec.scope is not None:
        if field(workspace, "authorized_access_scope") != spec.scope:
            gaps.append("authorized_access_scope")
        if field(workspace, "authorized_preserve_owner") != "true":
            gaps.append("authorized_preserve_owner")
    else:
        amount = field(workspace, "authorized_amount_minor") or ""
        currency = field(workspace, "authorized_currency") or ""
        if not re.fullmatch(r"0|[1-9][0-9]{0,11}", amount):
            gaps.append("authorized_amount_minor")
        elif spec.transfers_money and int(amount) == 0:
            gaps.append("positive_transfer_amount")
        elif workspace.case.impact_amount != Decimal(amount) / 100:
            gaps.append("matching_case_amount")
        if not re.fullmatch(r"[A-Z]{3}", currency) or workspace.case.impact_currency != currency:
            gaps.append("matching_case_currency")
    email = field(workspace, "requested_new_email")
    if (
        action_type == "change_recovery_email"
        and field(workspace, "challenge_destination") != email
    ):
        gaps.append("challenge_destination_match")
    if (
        action_type == "change_recovery_email"
        and email
        and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
    ):
        gaps.append("valid_new_email")
    return sorted(set(gaps))


def operation_draft(workspace: CaseWorkspaceRecord, action_type: str) -> ProposedActionDraft:
    gaps = operation_gaps(workspace, action_type)
    if gaps:
        raise ValueError("Operation parameters are incomplete: " + ", ".join(gaps))
    spec = OPERATIONS[action_type]
    mapping = {
        "external_reference": "requested_target",
        "recipient": "authorized_recipient",
        "reason_code": "authorized_reason_code",
        **{key: f"requested_{key}" for key in spec.value_fields},
    }
    mapping.update(
        {"access_scope": "authorized_access_scope", "preserve_owner": "authorized_preserve_owner"}
        if spec.scope
        else {"amount_minor": "authorized_amount_minor", "currency": "authorized_currency"}
    )
    parameters = {key: field(workspace, source) for key, source in mapping.items()}
    assert all(value is not None for value in parameters.values())
    return ProposedActionDraft(
        type=action_type,
        label=action_type.replace("_", " ").capitalize(),
        parameters={key: str(value) for key, value in parameters.items()},
        impact_amount=workspace.case.impact_amount if not spec.scope else None,
        impact_currency=workspace.case.impact_currency if not spec.scope else None,
        expected_outcome="The approved target change is independently read back before closure.",
        review_required=True,
    )
