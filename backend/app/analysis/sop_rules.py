"""Explicit, bounded SOP predicates. Natural-language policy is not executable code."""

import re
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.cases import CaseCategory, CaseWorkspaceRecord
from app.domain.controlled_operations import OPERATIONS, OperationType, operation_gaps
from app.domain.decision_briefs import InformationGap
from app.domain.policies import EvidenceRetrievalResult


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RefundWindow(Rule):
    kind: Literal["refund_window"]
    max_days: int = Field(ge=0, le=365)


class OwnershipProof(Rule):
    kind: Literal["ownership_proof"]
    required_level: Literal["verified", "independent_verified"]


class EscalationThreshold(Rule):
    kind: Literal["escalation_threshold"]
    max_amount_minor: int = Field(ge=0)
    currency: Literal["USD"]


class ControlledOperation(Rule):
    kind: Literal["controlled_operation"]
    action_type: OperationType
    max_amount_minor: int = Field(ge=0)
    currency: Literal["USD"]


class Rules(Rule):
    schema_version: Literal[1]
    rules: tuple[
        Annotated[
            RefundWindow | OwnershipProof | EscalationThreshold | ControlledOperation,
            Field(discriminator="kind"),
        ],
        ...,
    ] = Field(min_length=1, max_length=4)


def parse_rules(source: str) -> Rules | None:
    marker = "```case-resolution-rules"
    if marker not in source:
        return None
    matches = re.findall(r"```case-resolution-rules\s*\n(.*?)\n```", source, re.DOTALL)
    if len(matches) != 1 or source.count(marker) != 1:
        raise ValueError("SOP must contain exactly one complete rules block")
    parsed = Rules.model_validate_json(matches[0])
    kinds = [rule.kind for rule in parsed.rules]
    if len(kinds) != len(set(kinds)):
        raise ValueError("Duplicate SOP rule kinds are ambiguous")
    return parsed


def validate_rule_scope(source: str, categories: list[str]) -> None:
    rules = parse_rules(source)
    if rules is None:
        return
    for rule in rules.rules:
        if isinstance(rule, ControlledOperation):
            if categories != [OPERATIONS[rule.action_type].category]:
                raise ValueError("Controlled operation must match exactly one category")
            if OPERATIONS[rule.action_type].scope and rule.max_amount_minor != 0:
                raise ValueError("Identity operations cannot authorize a financial transfer")
        required = {"refund_window": "refund_request", "ownership_proof": "account_access"}.get(
            rule.kind
        )
        if required and categories != [required]:
            raise ValueError(f"{rule.kind} requires exactly the {required} category")
        if rule.kind == "escalation_threshold" and not set(categories) <= {
            "billing_dispute",
            "refund_request",
        }:
            raise ValueError("A monetary threshold requires billing or refund scope")


def _value(workspace: CaseWorkspaceRecord, key: str) -> str | None:
    # Contradictory records must not be resolved by list order.
    values = {str(item.fields[key]) for item in workspace.business_contexts if key in item.fields}
    return next(iter(values)) if len(values) == 1 else None


def _violation(rule: Rule, workspace: CaseWorkspaceRecord) -> str | None:
    if isinstance(rule, ControlledOperation):
        missing = operation_gaps(workspace, rule.action_type)
        if missing:
            return "Required operation evidence: " + ", ".join(missing)
        if not OPERATIONS[rule.action_type].scope and (
            workspace.case.impact_amount is None
            or workspace.case.impact_currency != rule.currency
            or workspace.case.impact_amount * 100 > rule.max_amount_minor
        ):
            return "The operation exceeds the published currency or amount authority."
    elif isinstance(rule, RefundWindow):
        if workspace.case.category is not CaseCategory.REFUND_REQUEST:
            return "Rule category does not match the case."
        raw = _value(workspace, "purchased_at")
        try:
            purchased = datetime.fromisoformat(raw or "")
            if purchased.tzinfo is None:
                raise ValueError("Purchase time needs a timezone")
            age = workspace.request.received_at - purchased
        except ValueError:
            return "An unambiguous timezone-aware purchase timestamp is required."
        if age < timedelta(0) or age > timedelta(days=rule.max_days):
            return f"Request is outside the inclusive {rule.max_days}-day refund window."
    elif isinstance(rule, OwnershipProof):
        if workspace.case.category is not CaseCategory.ACCOUNT_ACCESS:
            return "Rule category does not match the case."
        level = _value(workspace, "ownership_proof")
        allowed = {"independent_verified"}
        if rule.required_level == "verified":
            allowed.add("verified")
        if level not in allowed:
            return f"Ownership proof must be {rule.required_level}; unresolved conflicts escalate."
    elif isinstance(rule, EscalationThreshold):
        amount = workspace.case.impact_amount
        if amount is None or workspace.case.impact_currency != rule.currency:
            return "Escalation threshold requires a known amount in the policy currency."
        if amount * Decimal(100) > rule.max_amount_minor:
            return "Impact exceeds the SOP threshold; supervisor escalation is required."
    return None


def sop_gaps(
    workspace: CaseWorkspaceRecord, evidence: EvidenceRetrievalResult
) -> list[InformationGap]:
    gaps: list[InformationGap] = []
    seen: set[str] = set()
    kinds: set[str] = set()
    for bundle in evidence.evidence:
        version = bundle.version
        if version.public_id in seen:
            continue
        seen.add(version.public_id)
        try:
            rules = parse_rules(version.source_text)
            if rules is None:
                continue  # Existing prose-only policies retain their bounded legacy behavior.
            if (
                sha256(version.source_text.encode()).hexdigest() != version.content_hash
                or bundle.evidence.policy_content_hash != version.content_hash
                or version.organization_id != workspace.case.organization_id
                or bundle.evidence.case_id != workspace.case.id
            ):
                raise ValueError("Executable source must match the bound tenant, case and content")
            validate_rule_scope(version.source_text, version.case_categories)
            if not version.immutable or version.status.value not in {"published", "scheduled"}:
                raise ValueError("Rules require immutable published authority")
            at = bundle.evidence.recorded_at
            if (version.effective_from and at < version.effective_from) or (
                version.effective_to and at >= version.effective_to
            ):
                raise ValueError("Rules are outside their effective interval")
            for rule in rules.rules:
                if rule.kind in kinds:
                    raise ValueError("Multiple policies provide the same executable rule")
                kinds.add(rule.kind)
                detail = _violation(rule, workspace)
                if detail:
                    gaps.append(
                        InformationGap(
                            id=f"GAP-SOP-{rule.kind}",
                            label="SOP review required",
                            description=f"{rule.kind}: {detail} [{version.public_id}]",
                            blocking=True,
                        )
                    )
        except ValueError:
            gaps.append(
                InformationGap(
                    id="GAP-SOP-INVALID",
                    label="SOP configuration review",
                    description=(
                        "Executable SOP is invalid, ambiguous, or outside its authority window."
                    ),
                    blocking=True,
                )
            )
    return gaps
