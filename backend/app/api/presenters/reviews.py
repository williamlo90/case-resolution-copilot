from datetime import datetime

from app.api.presenters.decision_briefs import present_decision_brief
from app.api.schemas.cases import BusinessObjectSnapshotResponse
from app.api.schemas.common import (
    ActorSummaryResponse,
    MoneyResponse,
    SourceFreshnessResponse,
)
from app.api.schemas.policies import PolicyEvidenceResponse
from app.api.schemas.reviews import (
    ApprovalRuleResponse,
    ReviewDecisionReceiptResponse,
    ReviewReservationResponse,
    ReviewSnapshotFreshnessResponse,
    ReviewSnapshotResponse,
    ReviewSummaryResponse,
)
from app.domain.policies import PolicyEvidenceBundle
from app.domain.reviews import (
    ReviewDetailRecord,
    ReviewFreshnessRecord,
    ReviewQueueItemRecord,
)


def present_review_summary(
    item: ReviewQueueItemRecord,
    *,
    organization_id: str,
    now: datetime,
) -> ReviewSummaryResponse:
    bundle = item.bundle
    review = bundle.review
    return ReviewSummaryResponse(
        id=review.public_id,
        organization_id=organization_id,
        case_id=bundle.case_public_id,
        proposal={
            "id": item.proposal_public_id,
            "version": bundle.snapshot.proposal_version,
            "outcome": item.proposal_outcome,
        },
        impact=(
            MoneyResponse(
                amount=review.impact_amount,
                currency=review.impact_currency,
            )
            if review.impact_amount is not None and review.impact_currency is not None
            else None
        ),
        review_reason=review.review_reason,
        policy_state=review.policy_state.value,
        uncertainty=review.uncertainty.value,
        submitted_by=ActorSummaryResponse(
            id=review.submitted_by_public_id,
            name=review.submitted_by_name,
        ),
        submitted_at=review.submitted_at,
        waiting_minutes=max(0, int((now - review.submitted_at).total_seconds() // 60)),
        snapshot_freshness=_freshness(item.freshness),
        snapshot_fingerprint=bundle.snapshot.snapshot_fingerprint,
        status=review.status,
        reservation=(
            ReviewReservationResponse(
                id=bundle.reservation.public_id,
                reviewer=ActorSummaryResponse(
                    id=bundle.reservation.reviewer_public_id,
                    name=bundle.reservation.reviewer_name,
                ),
                reserved_at=bundle.reservation.reserved_at,
                expires_at=bundle.reservation.expires_at,
            )
            if bundle.reservation is not None
            else None
        ),
        version=review.version,
    )


def present_review_detail(
    detail: ReviewDetailRecord,
    *,
    organization_id: str,
    now: datetime,
) -> ReviewSnapshotResponse:
    bundle = detail.bundle
    decision_brief = present_decision_brief(
        detail.brief,
        organization_id=organization_id,
        case_id=bundle.case_public_id,
    )
    summary_item = ReviewQueueItemRecord(
        bundle=bundle,
        proposal_public_id=bundle.proposal_public_id,
        proposal_outcome=detail.brief.version.outcome,
        freshness=detail.freshness,
    )
    return ReviewSnapshotResponse(
        review=present_review_summary(
            summary_item,
            organization_id=organization_id,
            now=now,
        ),
        case_version=bundle.snapshot.case_version,
        context_fingerprint=bundle.snapshot.context_fingerprint,
        risk_rule_version=bundle.snapshot.risk_rule_version,
        facts=decision_brief.facts,
        business_contexts=[
            BusinessObjectSnapshotResponse(
                id=context.public_id,
                organization_id=organization_id,
                case_id=bundle.case_public_id,
                type=context.type.value,
                label=context.label,
                source=context.source,
                source_reference=context.source_reference,
                status=context.status,
                fields={key: str(value) for key, value in context.fields.items()},
                captured_at=context.captured_at,
                source_freshness=SourceFreshnessResponse(
                    status=context.source_freshness.value,
                    checked_at=context.source_checked_at,
                ),
                version=context.version,
            )
            for context in detail.business_contexts
        ],
        evidence=[_policy_evidence(item) for item in detail.evidence],
        risks=decision_brief.risks,
        proposal=decision_brief.proposal,
        actions=decision_brief.proposed_actions,
        approval_rule=ApprovalRuleResponse(
            id=bundle.snapshot.approval_rule_id,
            name=bundle.snapshot.approval_rule_name,
            explanation=bundle.snapshot.approval_rule_explanation,
            required_role=_role_label(bundle.snapshot.required_role.value),
            version=bundle.snapshot.approval_rule_version,
        ),
        available_decisions=detail.available_decisions,
        decision_history=[
            ReviewDecisionReceiptResponse(
                id=decision.public_id,
                review_id=bundle.review.public_id,
                decision=decision.decision,
                reason=decision.reason,
                actor=ActorSummaryResponse(
                    id=decision.reviewer_public_id,
                    name=decision.reviewer_name,
                ),
                snapshot_fingerprint=decision.snapshot_fingerprint,
                decided_at=decision.decided_at,
            )
            for decision in bundle.decisions
        ],
    )


def _freshness(value: ReviewFreshnessRecord) -> ReviewSnapshotFreshnessResponse:
    return ReviewSnapshotFreshnessResponse(
        status=value.status.value,
        checked_at=value.checked_at,
        reason=value.reason,
    )


def _policy_evidence(bundle: PolicyEvidenceBundle) -> PolicyEvidenceResponse:
    evidence = bundle.evidence
    effective_date = (
        evidence.effective_from.date().isoformat()
        if evidence.effective_from is not None
        else "Immediately effective"
    )
    return PolicyEvidenceResponse(
        id=evidence.public_id,
        policy_id=bundle.policy.public_id,
        policy_version_id=bundle.version.public_id,
        policy_version=bundle.version.version,
        clause_id=bundle.clause.public_id,
        title=bundle.policy.title,
        citation=evidence.citation,
        excerpt=evidence.excerpt,
        applicability=evidence.applicability,
        effective_date=effective_date,
        freshness=evidence.freshness,
        conflict_state=evidence.conflict_state,
        fingerprint=evidence.fingerprint,
    )


def _role_label(role: str) -> str:
    return {
        "supervisor": "Support supervisor",
        "administrator": "Operations administrator",
    }.get(role, role.replace("_", " ").title())
