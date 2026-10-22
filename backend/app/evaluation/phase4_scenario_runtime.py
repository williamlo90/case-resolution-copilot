"""Input-only mapping from a V2 scenario into the real case and synthetic target APIs."""

from datetime import timedelta
from decimal import Decimal

from app.domain.cases import (
    BusinessObjectCreate,
    BusinessObjectType,
    CaseCategory,
    CaseCreate,
    CaseRequestCreate,
    CaseRisk,
    CaseStatus,
    CaseUrgency,
    CustomerContextCreate,
    CustomerTier,
    RequestChannel,
    SourceFreshness,
)
from app.domain.controlled_operations import OPERATIONS
from app.evaluation.case_resolution_v2.models import Scenario

CATEGORY = {
    "billing": CaseCategory.BILLING_DISPUTE,
    "refund": CaseCategory.REFUND_REQUEST,
    "account_recovery": CaseCategory.ACCOUNT_ACCESS,
}
OBJECT_TYPE = {
    "billing": BusinessObjectType.INVOICE,
    "refund": BusinessObjectType.ORDER,
    "account_recovery": BusinessObjectType.ACCOUNT,
}


def product_case_id(scenario: Scenario) -> str:
    return "CS-" + scenario.case_id


def case_from_input(scenario: Scenario) -> CaseCreate:
    """Every business field comes from scenario evidence; no label path is reachable here."""
    if scenario.tenant_id != "ORG-0001":
        raise ValueError("Phase 4 scenario must name its isolated synthetic tenant")
    merged: dict[str, str] = {}
    conflicted: set[str] = set()
    for source in scenario.evidence:
        for key, value in source.facts.items():
            if key in conflicted:
                continue
            if key in merged and merged[key] != value:
                # Preserve the conflict in separate records, but never choose one value.
                merged.pop(key, None)
                conflicted.add(key)
            elif key not in merged:
                merged[key] = value
    operation = merged.get("requested_operation")
    category = CATEGORY[scenario.domain]
    if operation in OPERATIONS and OPERATIONS[operation].category != category.value:
        raise ValueError("Requested operation and case category disagree")
    if category is CaseCategory.ACCOUNT_ACCESS:
        impact_amount = None
        impact_currency = None
    else:
        minor = merged.get("authorized_amount_minor", "0")
        currency = merged.get("authorized_currency", "USD")
        if not minor.isascii() or not minor.isdecimal() or len(minor) > 12:
            raise ValueError("Invalid source amount")
        impact_amount = Decimal(minor) / 100
        impact_currency = currency
    contexts = [
        BusinessObjectCreate(
            public_id=f"CTX-{scenario.case_id}-{index}",
            type=OBJECT_TYPE[scenario.domain],
            label=f"Synthetic {scenario.domain} record {index}",
            source=source.id,
            source_reference=source.id,
            status="current",
            fields={**source.facts, "policy_scope": f"phase4:{scenario.family_id}".lower()},
            captured_at=scenario.as_of,
            freshness=SourceFreshness.CURRENT,
            checked_at=scenario.as_of,
        )
        for index, source in enumerate(scenario.evidence, start=1)
    ]
    return CaseCreate(
        public_id=product_case_id(scenario),
        source_id=f"phase4:{scenario.case_id}",
        external_reference=merged.get("requested_target", scenario.case_id),
        category=category,
        issue=scenario.request,
        status=CaseStatus.INVESTIGATING,
        urgency=CaseUrgency.HIGH if scenario.critical else CaseUrgency.MEDIUM,
        risk=CaseRisk.HIGH if scenario.critical else CaseRisk.MEDIUM,
        due_at=scenario.deadline,
        impact_amount=impact_amount,
        impact_currency=impact_currency,
        source_freshness=SourceFreshness.CURRENT,
        source_checked_at=scenario.as_of,
        request=CaseRequestCreate(
            channel=RequestChannel.EMAIL,
            customer_message=scenario.request,
            summary=scenario.request,
            received_at=scenario.as_of - timedelta(minutes=1),
        ),
        customer=CustomerContextCreate(
            customer_id=f"CUSTOMER-{scenario.case_id}",
            name="Synthetic Case Owner",
            tier=CustomerTier.STANDARD,
            locale="en-US",
            contact=f"{scenario.case_id.lower()}@example.test",
        ),
        business_contexts=contexts,
    )


def target_from_input(scenario: Scenario) -> dict[str, dict[str, str]]:
    """Construct a target state only from recorded source facts, never expected effects."""
    source_facts = [item.facts for item in scenario.evidence]
    operations = {item.get("requested_operation") for item in source_facts}
    if len(operations - {None}) != 1:
        return {}
    values = {key: value for facts in source_facts for key, value in facts.items()}
    target = values.get("requested_target")
    owner = values.get("target_owner")
    if not target or not owner:
        return {}
    state = {"owner": owner}
    mapping = {
        "target_current_currency": "currency",
        "target_current_name": "new_name",
        "target_current_address": "new_address",
        "target_current_recovery_email": "new_email",
        "target_active_sessions": "active_sessions",
    }
    state.update({name: values[key] for key, name in mapping.items() if key in values})
    if values.get("invoice_state"):
        state["invoice_state"] = values["invoice_state"]
    if values.get("authorized_currency"):
        state.setdefault("currency", values["authorized_currency"])
    state.setdefault("credited_minor", "0")
    return {target: state}
