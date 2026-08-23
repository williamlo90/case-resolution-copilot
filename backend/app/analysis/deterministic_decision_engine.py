import json
from decimal import Decimal
from hashlib import sha256
from typing import Protocol

from app.domain.cases import (
    BusinessObjectRecord,
    BusinessObjectType,
    CaseCategory,
    CaseWorkspaceRecord,
    CustomerTier,
    SourceFreshness,
)
from app.domain.decision_briefs import (
    AnalysisCheckpointDraft,
    AnalysisStatus,
    CheckpointStatus,
    DecisionAnalysis,
    DecisionProposalState,
    DecisionRiskCheck,
    InformationGap,
    ProposalConfidence,
    ProposedActionDraft,
    ResponseSuggestionStatus,
    RiskOutcome,
    SuggestedResponseDraft,
    VerifiedFact,
)
from app.domain.policies import EvidenceRetrievalResult, EvidenceRetrievalStatus

DECISION_MODEL_VERSION = "deterministic-decision-engine-v1"
DECISION_PROMPT_VERSION = "decision-brief-rules-v1"
DECISION_GRAPH_VERSION = "generic-decision-brief-v1"
DECISION_RISK_RULE_VERSION = "generic-risk-rules-v1"


class DecisionEngine(Protocol):
    model_version: str
    prompt_version: str
    graph_version: str
    risk_rule_version: str

    def analyze(
        self,
        *,
        workspace: CaseWorkspaceRecord,
        evidence: EvidenceRetrievalResult,
        input_fingerprint: str,
    ) -> DecisionAnalysis: ...


def context_snapshot_fingerprint(context: BusinessObjectRecord) -> str:
    payload = {
        "public_id": context.public_id,
        "version": context.version,
        "type": context.type.value,
        "status": context.status,
        "source": context.source,
        "source_reference": context.source_reference,
        "fields": dict(sorted((key, str(value)) for key, value in context.fields.items())),
        "captured_at": context.captured_at.isoformat(),
        "source_freshness": context.source_freshness.value,
        "source_checked_at": (
            context.source_checked_at.isoformat() if context.source_checked_at else None
        ),
    }
    return _hash(payload)


def combined_context_fingerprint(workspace: CaseWorkspaceRecord) -> str:
    return _hash(
        [
            {
                "id": context.public_id,
                "fingerprint": context_snapshot_fingerprint(context),
            }
            for context in sorted(workspace.business_contexts, key=lambda item: item.public_id)
        ]
    )


def combined_evidence_fingerprint(evidence: EvidenceRetrievalResult) -> str:
    return _hash(
        {
            "status": evidence.status.value,
            "evidence": sorted(bundle.evidence.fingerprint for bundle in evidence.evidence),
        }
    )


def decision_input_fingerprint(
    *,
    workspace: CaseWorkspaceRecord,
    evidence: EvidenceRetrievalResult,
    context_fingerprint: str,
    evidence_fingerprint: str,
    model_version: str = DECISION_MODEL_VERSION,
    prompt_version: str = DECISION_PROMPT_VERSION,
    graph_version: str = DECISION_GRAPH_VERSION,
    risk_rule_version: str = DECISION_RISK_RULE_VERSION,
) -> str:
    return _hash(
        {
            "case_id": workspace.case.public_id,
            "case_version": workspace.case.version,
            "category": workspace.case.category.value,
            "request": workspace.request.summary,
            "context_fingerprint": context_fingerprint,
            "evidence_fingerprint": evidence_fingerprint,
            "policy_status": evidence.status.value,
            "model_version": model_version,
            "prompt_version": prompt_version,
            "graph_version": graph_version,
            "risk_rule_version": risk_rule_version,
        }
    )


class DeterministicDecisionEngine:
    model_version = DECISION_MODEL_VERSION
    prompt_version = DECISION_PROMPT_VERSION
    graph_version = DECISION_GRAPH_VERSION
    risk_rule_version = DECISION_RISK_RULE_VERSION

    def analyze(
        self,
        *,
        workspace: CaseWorkspaceRecord,
        evidence: EvidenceRetrievalResult,
        input_fingerprint: str,
    ) -> DecisionAnalysis:
        facts = _facts(workspace)
        gaps = _information_gaps(workspace, evidence.status)
        blocking = [gap for gap in gaps if gap.blocking]
        risks = _risk_checks(workspace, evidence.status, blocking)
        state = (
            DecisionProposalState.INFORMATION_NEEDED
            if evidence.status is not EvidenceRetrievalStatus.RELEVANT or blocking
            else DecisionProposalState.READY_FOR_REVIEW
        )
        confidence = _confidence(workspace, evidence.status, blocking)
        outcome = _outcome(workspace.case.category, state, evidence.status)
        impact_amount = None
        impact_currency = None
        if state is DecisionProposalState.READY_FOR_REVIEW and workspace.case.category in {
            CaseCategory.BILLING_DISPUTE,
            CaseCategory.REFUND_REQUEST,
        }:
            impact_amount = workspace.case.impact_amount
            impact_currency = workspace.case.impact_currency
        actions = _actions(
            workspace=workspace,
            state=state,
            gaps=blocking,
            impact_amount=impact_amount,
            impact_currency=impact_currency,
        )
        uncertainty = _uncertainty(evidence.status, blocking, workspace)
        rationale = _rationale(evidence.status, facts, blocking, risks)
        response = _response(workspace.case.category, state, blocking)
        status = (
            AnalysisStatus.COMPLETED
            if evidence.status is EvidenceRetrievalStatus.RELEVANT
            else AnalysisStatus.ABSTAINED
        )
        checkpoints = _checkpoints(
            input_fingerprint=input_fingerprint,
            evidence=evidence,
            facts=facts,
            gaps=gaps,
            risks=risks,
            outcome=outcome,
            status=status,
        )
        return DecisionAnalysis(
            status=status,
            policy_status=evidence.status,
            facts=facts,
            missing_information=gaps,
            risks=risks,
            outcome=outcome,
            impact_amount=impact_amount,
            impact_currency=impact_currency,
            confidence=confidence,
            uncertainty=uncertainty,
            rationale=rationale,
            state=state,
            proposed_actions=actions,
            response_draft=response,
            checkpoints=checkpoints,
            risk_rule_version=DECISION_RISK_RULE_VERSION,
            model_version=DECISION_MODEL_VERSION,
            prompt_version=DECISION_PROMPT_VERSION,
            graph_version=DECISION_GRAPH_VERSION,
        )


def _facts(workspace: CaseWorkspaceRecord) -> list[VerifiedFact]:
    facts: list[VerifiedFact] = []
    field_labels = {
        "amount": "Amount",
        "currency": "Currency",
        "delivery_state": "Delivery state",
        "attempt_count": "Recorded payment attempts",
        "identity_check": "Identity check",
        "mfa_state": "Multi-factor authentication",
    }
    for context in workspace.business_contexts:
        verified_at = context.source_checked_at or context.captured_at
        source = f"{context.source} / {context.source_reference}"
        statement = f"{context.label} is recorded with status {context.status}."
        facts.append(
            VerifiedFact(
                id=_public_id("FCT", workspace.case.public_id, context.public_id, "status"),
                statement=statement,
                source=source,
                verified_at=verified_at,
            )
        )
        for key, label in field_labels.items():
            value = context.fields.get(key)
            if value is None:
                continue
            facts.append(
                VerifiedFact(
                    id=_public_id("FCT", workspace.case.public_id, context.public_id, key),
                    statement=f"{label}: {value}.",
                    source=source,
                    verified_at=verified_at,
                )
            )
    return facts


def _information_gaps(
    workspace: CaseWorkspaceRecord, policy_status: EvidenceRetrievalStatus
) -> list[InformationGap]:
    gaps: list[InformationGap] = []
    if workspace.collections.business_contexts.has_more:
        gaps.append(
            _gap(
                workspace.case.public_id,
                "complete-business-context",
                "Complete business records",
                (
                    "This case has more business records than the decision workspace can "
                    "safely evaluate at once. Narrow or consolidate the relevant records "
                    "before preparing a final resolution."
                ),
            )
        )
    if policy_status is not EvidenceRetrievalStatus.RELEVANT:
        gaps.append(
            _gap(
                workspace.case.public_id,
                "applicable-policy",
                "Applicable policy",
                _policy_gap_description(policy_status),
            )
        )
    stale = [
        context.label
        for context in workspace.business_contexts
        if context.source_freshness is not SourceFreshness.CURRENT
    ]
    if workspace.case.source_freshness is not SourceFreshness.CURRENT or stale:
        labels = ", ".join(stale) if stale else "case source"
        gaps.append(
            _gap(
                workspace.case.public_id,
                "current-source-context",
                "Current source context",
                f"Refresh {labels} before relying on the proposed outcome.",
            )
        )

    category = workspace.case.category
    if category is CaseCategory.BILLING_DISPUTE:
        payment_references = {
            context.source_reference
            for context in workspace.business_contexts
            if context.type is BusinessObjectType.PAYMENT
            and context.status == "settled"
        }
        if len(payment_references) < 2:
            gaps.append(
                _gap(
                    workspace.case.public_id,
                    "second-payment-reference",
                    "Second payment reference",
                    "Confirm a second settled payment reference before treating the charge as a "
                    "duplicate.",
                )
            )
    elif category is CaseCategory.REFUND_REQUEST:
        eligible_order = any(
            context.type is BusinessObjectType.ORDER
            and context.status == "unused"
            and str(context.fields.get("delivery_state", "")) == "not_started"
            for context in workspace.business_contexts
        )
        if not eligible_order:
            gaps.append(
                _gap(
                    workspace.case.public_id,
                    "delivery-status",
                    "Service delivery status",
                    "Confirm that service delivery has not started before proposing a refund.",
                )
            )
    elif category is CaseCategory.ACCOUNT_ACCESS:
        verified_identity = any(
            context.type is BusinessObjectType.ACCOUNT
            and str(context.fields.get("identity_check", "")) == "verified"
            for context in workspace.business_contexts
        )
        if not verified_identity:
            gaps.append(
                _gap(
                    workspace.case.public_id,
                    "identity-verification",
                    "Identity verification",
                    "Complete the account ownership check before changing a recovery channel.",
                )
            )
    elif category is CaseCategory.SERVICE_EXCEPTION:
        failed_service = any(
            context.status in {"failed", "incomplete", "not_delivered"}
            for context in workspace.business_contexts
        )
        if not failed_service:
            gaps.append(
                _gap(
                    workspace.case.public_id,
                    "service-outcome",
                    "Service outcome",
                    "Confirm the failed or incomplete service outcome before proposing a "
                    "correction.",
                )
            )
    return _deduplicate_gaps(gaps)


def _risk_checks(
    workspace: CaseWorkspaceRecord,
    policy_status: EvidenceRetrievalStatus,
    blocking: list[InformationGap],
) -> list[DecisionRiskCheck]:
    policy_outcome = (
        RiskOutcome.PASSED
        if policy_status is EvidenceRetrievalStatus.RELEVANT
        else RiskOutcome.BLOCKED
    )
    source_current = workspace.case.source_freshness is SourceFreshness.CURRENT and all(
        context.source_freshness is SourceFreshness.CURRENT
        for context in workspace.business_contexts
    )
    requires_review = (
        workspace.case.impact_amount is not None
        or workspace.customer.tier in {CustomerTier.VIP, CustomerTier.ENTERPRISE}
        or workspace.case.category is CaseCategory.ACCOUNT_ACCESS
        or workspace.case.risk.value == "high"
    )
    return [
        _risk(
            workspace.case.public_id,
            "policy-authority",
            "Policy authority",
            policy_outcome,
            (
                "Published policy evidence supports this decision brief."
                if policy_outcome is RiskOutcome.PASSED
                else "Applicable published policy evidence is not available; no consequential "
                "action may proceed."
            ),
        ),
        _risk(
            workspace.case.public_id,
            "source-freshness",
            "Source freshness",
            RiskOutcome.PASSED if source_current else RiskOutcome.INFORMATION_NEEDED,
            (
                "Case and business context sources are current."
                if source_current
                else "One or more source snapshots must be refreshed."
            ),
        ),
        _risk(
            workspace.case.public_id,
            "information-completeness",
            "Information completeness",
            RiskOutcome.INFORMATION_NEEDED if blocking else RiskOutcome.PASSED,
            (
                f"{len(blocking)} blocking information item(s) remain."
                if blocking
                else "No blocking information gap was found by deterministic checks."
            ),
        ),
        _risk(
            workspace.case.public_id,
            "human-authority",
            "Human authority",
            RiskOutcome.REQUIRES_REVIEW if requires_review else RiskOutcome.PASSED,
            (
                "Customer tier, financial impact, case risk, or account sensitivity requires "
                "review."
                if requires_review
                else "No deterministic review trigger was found."
            ),
        ),
    ]


def _confidence(
    workspace: CaseWorkspaceRecord,
    policy_status: EvidenceRetrievalStatus,
    blocking: list[InformationGap],
) -> ProposalConfidence:
    if policy_status is not EvidenceRetrievalStatus.RELEVANT or blocking:
        return ProposalConfidence.LOW
    if workspace.case.risk.value == "low" and workspace.customer.tier is CustomerTier.STANDARD:
        return ProposalConfidence.HIGH
    return ProposalConfidence.MEDIUM


def _outcome(
    category: CaseCategory,
    state: DecisionProposalState,
    policy_status: EvidenceRetrievalStatus,
) -> str:
    if policy_status is not EvidenceRetrievalStatus.RELEVANT:
        return "Pause the resolution until applicable policy is available"
    if state is DecisionProposalState.INFORMATION_NEEDED:
        return {
            CaseCategory.BILLING_DISPUTE: "Verify the second charge before a billing adjustment",
            CaseCategory.REFUND_REQUEST: "Confirm delivery status before a refund decision",
            CaseCategory.ACCOUNT_ACCESS: "Complete identity verification before account recovery",
            CaseCategory.SERVICE_EXCEPTION: "Confirm the service failure before a correction",
        }[category]
    return {
        CaseCategory.BILLING_DISPUTE: "Reverse the verified duplicate charge",
        CaseCategory.REFUND_REQUEST: "Approve refund for the unused service order",
        CaseCategory.ACCOUNT_ACCESS: "Start verified account recovery",
        CaseCategory.SERVICE_EXCEPTION: "Approve the documented service correction",
    }[category]


def _actions(
    *,
    workspace: CaseWorkspaceRecord,
    state: DecisionProposalState,
    gaps: list[InformationGap],
    impact_amount: Decimal | None,
    impact_currency: str | None,
) -> list[ProposedActionDraft]:
    if state is DecisionProposalState.INFORMATION_NEEDED:
        return [
            ProposedActionDraft(
                type="request_information",
                label="Request the missing information",
                parameters={"items": "; ".join(gap.label for gap in gaps)},
                impact_amount=None,
                impact_currency=None,
                expected_outcome="Blocking information is recorded before the decision is revised.",
                review_required=False,
            )
        ]
    action_type, label, expected = {
        CaseCategory.BILLING_DISPUTE: (
            "reverse_duplicate_charge",
            "Reverse the duplicate charge",
            "The verified duplicate charge is reversed with an attributable reference.",
        ),
        CaseCategory.REFUND_REQUEST: (
            "issue_refund",
            "Issue the approved refund",
            "The unused service order is refunded with an attributable reference.",
        ),
        CaseCategory.ACCOUNT_ACCESS: (
            "start_verified_recovery",
            "Start verified account recovery",
            "The verified owner receives a controlled recovery path.",
        ),
        CaseCategory.SERVICE_EXCEPTION: (
            "apply_service_correction",
            "Apply the approved service correction",
            "The documented service failure is corrected with an attributable reference.",
        ),
    }[workspace.case.category]
    return [
        ProposedActionDraft(
            type=action_type,
            label=label,
            parameters={
                "case_id": workspace.case.public_id,
                "external_reference": workspace.case.external_reference,
            },
            impact_amount=impact_amount,
            impact_currency=impact_currency,
            expected_outcome=expected,
            review_required=True,
        )
    ]


def _uncertainty(
    policy_status: EvidenceRetrievalStatus,
    blocking: list[InformationGap],
    workspace: CaseWorkspaceRecord,
) -> str:
    if policy_status is not EvidenceRetrievalStatus.RELEVANT:
        return _policy_gap_description(policy_status)
    if blocking:
        return (
            "The outcome remains uncertain until: "
            + "; ".join(gap.label.lower() for gap in blocking)
            + "."
        )
    if workspace.case.risk.value == "high":
        return (
            "The evidence supports the outcome, but the high-risk case still requires human review."
        )
    return "No blocking uncertainty was found; human review still governs the proposed action."


def _rationale(
    policy_status: EvidenceRetrievalStatus,
    facts: list[VerifiedFact],
    blocking: list[InformationGap],
    risks: list[DecisionRiskCheck],
) -> str:
    if policy_status is not EvidenceRetrievalStatus.RELEVANT:
        return (
            "The brief abstains because applicable policy authority is not usable. "
            "It records a safe next step without authorizing a customer-impacting action."
        )
    review_count = sum(risk.outcome is RiskOutcome.REQUIRES_REVIEW for risk in risks)
    if blocking:
        return (
            f"{len(facts)} source-backed fact(s) are recorded, but {len(blocking)} blocking "
            "information item(s) prevent a final resolution."
        )
    return (
        f"{len(facts)} source-backed fact(s) and published policy evidence support the proposed "
        f"outcome. {review_count} deterministic authority check(s) require human review."
    )


def _response(
    category: CaseCategory,
    state: DecisionProposalState,
    blocking: list[InformationGap],
) -> SuggestedResponseDraft:
    if state is DecisionProposalState.INFORMATION_NEEDED:
        needed = ", ".join(gap.label.lower() for gap in blocking) or "policy confirmation"
        return SuggestedResponseDraft(
            subject="Update on your support case",
            body=(
                "We are reviewing your case. Before confirming an outcome, we need to verify "
                f"{needed}. We will update you after that check is complete."
            ),
            status=ResponseSuggestionStatus.BLOCKED,
        )
    category_text = {
        CaseCategory.BILLING_DISPUTE: "the duplicate charge",
        CaseCategory.REFUND_REQUEST: "the refund request",
        CaseCategory.ACCOUNT_ACCESS: "the account recovery request",
        CaseCategory.SERVICE_EXCEPTION: "the service correction",
    }[category]
    return SuggestedResponseDraft(
        subject="Proposed resolution for your support case",
        body=(
            f"We reviewed the available records and prepared a resolution for {category_text}. "
            "The proposed action is pending the required human review before any change is made."
        ),
        status=ResponseSuggestionStatus.READY,
    )


def _checkpoints(
    *,
    input_fingerprint: str,
    evidence: EvidenceRetrievalResult,
    facts: list[VerifiedFact],
    gaps: list[InformationGap],
    risks: list[DecisionRiskCheck],
    outcome: str,
    status: AnalysisStatus,
) -> list[AnalysisCheckpointDraft]:
    payloads = [
        (
            "case_context",
            CheckpointStatus.COMPLETED,
            "Persisted case and business context snapshots were read.",
            {"facts": len(facts), "gaps": len(gaps)},
        ),
        (
            "policy_evidence",
            (
                CheckpointStatus.COMPLETED
                if evidence.status is EvidenceRetrievalStatus.RELEVANT
                else CheckpointStatus.ABSTAINED
            ),
            evidence.reason,
            {
                "status": evidence.status.value,
                "fingerprints": sorted(item.evidence.fingerprint for item in evidence.evidence),
            },
        ),
        (
            "risk_evaluation",
            CheckpointStatus.COMPLETED,
            "Deterministic risk and authority checks were evaluated.",
            [risk.model_dump(mode="json") for risk in risks],
        ),
        (
            "decision_brief",
            (
                CheckpointStatus.COMPLETED
                if status is AnalysisStatus.COMPLETED
                else CheckpointStatus.ABSTAINED
            ),
            "A business-readable decision brief was recorded.",
            {"outcome": outcome, "analysis_status": status.value},
        ),
    ]
    checkpoints: list[AnalysisCheckpointDraft] = []
    previous = input_fingerprint
    for sequence, (step, checkpoint_status, summary, output) in enumerate(payloads, start=1):
        output_fingerprint = _hash(output)
        checkpoints.append(
            AnalysisCheckpointDraft(
                sequence=sequence,
                step=step,
                status=checkpoint_status,
                summary=summary,
                input_fingerprint=previous,
                output_fingerprint=output_fingerprint,
            )
        )
        previous = output_fingerprint
    return checkpoints


def _gap(case_id: str, key: str, label: str, description: str) -> InformationGap:
    return InformationGap(
        id=_public_id("GAP", case_id, key),
        label=label,
        description=description,
        blocking=True,
    )


def _risk(
    case_id: str,
    key: str,
    label: str,
    outcome: RiskOutcome,
    explanation: str,
) -> DecisionRiskCheck:
    return DecisionRiskCheck(
        id=_public_id("RSK", case_id, key),
        label=label,
        outcome=outcome,
        explanation=explanation,
    )


def _policy_gap_description(status: EvidenceRetrievalStatus) -> str:
    return {
        EvidenceRetrievalStatus.MISSING: "No published policy currently covers this case.",
        EvidenceRetrievalStatus.INAPPLICABLE: (
            "Published policies exist but do not match this case context."
        ),
        EvidenceRetrievalStatus.STALE: (
            "Matching policy versions are outside their effective dates."
        ),
        EvidenceRetrievalStatus.CONFLICTING: (
            "Published policies claim conflicting authority for this decision."
        ),
        EvidenceRetrievalStatus.RELEVANT: "Published policy evidence is available.",
    }[status]


def _deduplicate_gaps(gaps: list[InformationGap]) -> list[InformationGap]:
    unique: dict[str, InformationGap] = {}
    for gap in gaps:
        unique.setdefault(gap.id, gap)
    return list(unique.values())


def _public_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
