from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.domain.cases import CaseConcurrencyConflict
from app.domain.decision_briefs import DecisionProposalState
from app.domain.identity import MemberRole, role_satisfies
from app.domain.reviews import (
    ReviewAuthorityDenied,
    ReviewBundleRecord,
    ReviewConflict,
    ReviewDecision,
    ReviewNotFound,
    ReviewReservationExpired,
    ReviewReservationStatus,
    ReviewSnapshotStale,
    ReviewStatus,
    ReviewSubmission,
    ReviewVersionConflict,
)
from app.persistence.models import (
    AuditEventModel,
    CaseModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseReviewDecisionModel,
    CaseReviewModel,
    CaseReviewReservationModel,
    CaseReviewSnapshotModel,
    ProposalResponseDraftModel,
    ResponseDraftModel,
    utc_now,
)

from ._base import (
    REVIEW_HOLD_MINUTES,
    TERMINAL_REVIEW_STATUSES,
    ReviewRepositoryBase,
    _decision_label,
    _proposal_state,
    _review_status,
    _stable_public_id,
)


class ReviewWorkflowRepository(ReviewRepositoryBase):
    def submit(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        actor_id: str,
        command: ReviewSubmission,
        correlation_id: str,
    ) -> ReviewBundleRecord:
        scoped = self._scoped_case(
            organization_public_id,
            case_public_id,
            for_update=True,
        )
        if scoped is None:
            raise ReviewNotFound("The case was not found.")
        _, case = scoped
        proposal = self._session.scalar(
            select(CaseProposalModel).where(
                CaseProposalModel.organization_id == case.organization_id,
                CaseProposalModel.case_id == case.id,
            )
        )
        if proposal is None:
            raise ReviewNotFound("The proposal was not found.")
        version = self._session.scalar(
            select(CaseProposalVersionModel).where(
                CaseProposalVersionModel.organization_id == case.organization_id,
                CaseProposalVersionModel.case_id == case.id,
                CaseProposalVersionModel.proposal_id == proposal.id,
                CaseProposalVersionModel.version == command.proposal_version,
            )
        )
        if version is None:
            raise ReviewNotFound("The proposal version was not found.")
        existing = self._session.scalar(
            select(CaseReviewModel).where(
                CaseReviewModel.organization_id == case.organization_id,
                CaseReviewModel.case_id == case.id,
                CaseReviewModel.proposal_version_id == version.id,
            )
        )
        if existing is not None:
            return self._load_bundle(existing, now=utc_now())
        self._require_approval_rule_version(
            organization_id=case.organization_id,
            expected_version=command.approval_rule.version,
        )
        if proposal.current_version != command.proposal_version:
            raise ReviewConflict(
                "A newer resolution exists. Open the current version before submitting a review."
            )
        if case.version != command.expected_case_version:
            raise CaseConcurrencyConflict(
                expected_version=command.expected_case_version,
                current_version=case.version,
            )
        member = self._active_member(
            organization_id=case.organization_id,
            actor_id=actor_id,
        )
        new_case_version = case.version + 1
        now = utc_now()
        case.status = "needs_review"
        case.version = new_case_version
        case.updated_at = now

        review = CaseReviewModel(
            public_id=_stable_public_id(
                "RV", organization_public_id, case.public_id, version.public_id
            ),
            organization_id=case.organization_id,
            case_id=case.id,
            proposal_id=proposal.id,
            proposal_version_id=version.id,
            status=ReviewStatus.PENDING.value,
            review_reason=command.review_reason,
            policy_state=command.policy_state.value,
            uncertainty=command.uncertainty.value,
            impact_amount=command.impact_amount,
            impact_currency=command.impact_currency,
            submitted_by_id=member.id,
            submitted_by_public_id=member.public_id,
            submitted_by_name=member.name,
            submitted_by_role=member.role,
            submitted_at=now,
            version=1,
            updated_at=now,
        )
        self._session.add(review)
        self._session.flush()
        snapshot = CaseReviewSnapshotModel(
            public_id=_stable_public_id("RVS", review.public_id),
            organization_id=case.organization_id,
            case_id=case.id,
            review_id=review.id,
            proposal_id=proposal.id,
            proposal_version_id=version.id,
            case_version=new_case_version,
            proposal_version=command.proposal_version,
            proposal_fingerprint=command.proposal_fingerprint,
            context_fingerprint=command.context_fingerprint,
            evidence_fingerprint=command.evidence_fingerprint,
            risk_fingerprint=command.risk_fingerprint,
            risk_rule_version=command.risk_rule_version,
            snapshot_fingerprint=command.snapshot_fingerprint,
            approval_rule_id=command.approval_rule.public_id,
            approval_rule_name=command.approval_rule.name,
            approval_rule_explanation=command.approval_rule.explanation,
            required_role=command.approval_rule.required_role.value,
            approval_rule_version=command.approval_rule.version,
            execution_eligible=command.execution_eligible,
            created_at=now,
        )
        self._session.add(snapshot)
        self._session.add(
            AuditEventModel(
                organization_id=case.organization_id,
                task_id=None,
                run_id=None,
                event_type="case.review_submitted",
                actor_type="member",
                actor_id=member.public_id,
                subject_type="review",
                subject_id=review.public_id,
                summary="Resolution submitted for human review.",
                data={
                    "case_id": case.public_id,
                    "proposal_id": proposal.public_id,
                    "proposal_version": version.version,
                    "snapshot_fingerprint": command.snapshot_fingerprint,
                    "required_role": command.approval_rule.required_role.value,
                },
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )
        self._session.flush()
        return self._load_bundle(review, now=now)

    def reserve(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
        actor_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> ReviewBundleRecord:
        review = self._required_review(
            organization_public_id,
            review_public_id,
            for_update=True,
        )
        now = utc_now()
        self._reconcile_expired(review=review, now=now)
        active = self._active_reservation(review, now=now)
        member = self._active_member(
            organization_id=review.organization_id,
            actor_id=actor_id,
        )
        if active is not None and active.reviewer_id == member.id:
            return self._load_bundle(review, now=now)
        if review.version != expected_version:
            raise ReviewVersionConflict(
                expected_version=expected_version,
                current_version=review.version,
            )
        if review.status in TERMINAL_REVIEW_STATUSES:
            raise ReviewConflict("This review already has a final decision.")
        if active is not None:
            raise ReviewConflict("This review is currently reserved by another reviewer.")
        if review.submitted_by_id == member.id:
            raise ReviewConflict("A resolution must be reviewed by a different person.")
        snapshot = self._required_snapshot(review)
        self._require_approval_rule_version(
            organization_id=review.organization_id,
            expected_version=snapshot.approval_rule_version,
        )
        reservation = CaseReviewReservationModel(
            public_id=_stable_public_id("RVR", review.public_id, member.public_id, str(uuid4())),
            organization_id=review.organization_id,
            case_id=review.case_id,
            review_id=review.id,
            snapshot_id=snapshot.id,
            reviewer_id=member.id,
            legacy_reservation_id=None,
            reviewer_public_id=member.public_id,
            reviewer_name=member.name,
            reviewer_role=member.role,
            snapshot_fingerprint=snapshot.snapshot_fingerprint,
            status=ReviewReservationStatus.ACTIVE.value,
            reserved_at=now,
            expires_at=now + timedelta(minutes=REVIEW_HOLD_MINUTES),
        )
        self._session.add(reservation)
        review.status = ReviewStatus.RESERVED.value
        review.version += 1
        review.updated_at = now
        self._set_proposal_state(review, DecisionProposalState.UNDER_REVIEW, now=now)
        self._session.add(
            AuditEventModel(
                organization_id=review.organization_id,
                task_id=None,
                run_id=None,
                event_type="case.review_reserved",
                actor_type="member",
                actor_id=member.public_id,
                subject_type="review",
                subject_id=review.public_id,
                summary="Review reserved for a human decision.",
                data={
                    "reservation_id": reservation.public_id,
                    "expires_at": reservation.expires_at.isoformat(),
                    "snapshot_fingerprint": snapshot.snapshot_fingerprint,
                },
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )
        self._session.flush()
        return self._load_bundle(review, now=now)

    def decide(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
        actor_id: str,
        expected_version: int,
        snapshot_fingerprint: str,
        decision: ReviewDecision,
        reason: str,
        correlation_id: str,
    ) -> ReviewBundleRecord:
        review = self._required_review(
            organization_public_id,
            review_public_id,
            for_update=True,
        )
        now = utc_now()
        if review.version != expected_version:
            raise ReviewVersionConflict(
                expected_version=expected_version,
                current_version=review.version,
            )
        if review.status in TERMINAL_REVIEW_STATUSES:
            raise ReviewConflict("This review already has a final decision.")
        snapshot = self._required_snapshot(review)
        if snapshot.snapshot_fingerprint != snapshot_fingerprint:
            raise ReviewConflict("The submitted review snapshot does not match this review.")
        self._require_approval_rule_version(
            organization_id=review.organization_id,
            expected_version=snapshot.approval_rule_version,
        )
        case = self._session.scalar(
            select(CaseModel)
            .where(
                CaseModel.id == review.case_id,
                CaseModel.organization_id == review.organization_id,
            )
            .with_for_update()
        )
        proposal = self._session.scalar(
            select(CaseProposalModel)
            .where(
                CaseProposalModel.id == review.proposal_id,
                CaseProposalModel.organization_id == review.organization_id,
            )
            .with_for_update()
        )
        if case is None or proposal is None:
            raise ReviewConflict("The reviewed case or resolution is no longer available.")
        if (
            case.version != snapshot.case_version
            or proposal.current_version != snapshot.proposal_version
        ):
            raise ReviewSnapshotStale(
                "The case or resolution changed after this review was submitted."
            )
        reservation = self._session.scalar(
            select(CaseReviewReservationModel).where(
                CaseReviewReservationModel.organization_id == review.organization_id,
                CaseReviewReservationModel.case_id == review.case_id,
                CaseReviewReservationModel.review_id == review.id,
                CaseReviewReservationModel.status == ReviewReservationStatus.ACTIVE.value,
            )
        )
        if reservation is None:
            raise ReviewConflict("Reserve this review before recording a decision.")
        if reservation.expires_at <= now:
            raise ReviewReservationExpired(
                "The review reservation expired. Reserve the review again before deciding."
            )
        member = self._active_member(
            organization_id=review.organization_id,
            actor_id=actor_id,
            for_update=True,
        )
        if reservation.reviewer_id != member.id:
            raise ReviewConflict("The review is reserved by another reviewer.")
        if reservation.snapshot_fingerprint != snapshot_fingerprint:
            raise ReviewConflict("The reserved snapshot no longer matches this review.")
        if not role_satisfies(
            actor_role=MemberRole(member.role),
            required_role=MemberRole(snapshot.required_role),
        ):
            raise ReviewAuthorityDenied(
                "Your current role does not have authority to decide this review."
            )
        freshness = self._freshness(review, now=now, for_update=True)
        if freshness.status.value != "current":
            raise ReviewSnapshotStale(
                freshness.reason or "The review snapshot is stale and cannot be decided."
            )

        decision_model = CaseReviewDecisionModel(
            public_id=_stable_public_id("RVD", review.public_id, str(review.version)),
            organization_id=review.organization_id,
            case_id=review.case_id,
            review_id=review.id,
            reservation_id=reservation.id,
            reviewer_id=member.id,
            legacy_decision_id=None,
            reviewer_public_id=member.public_id,
            reviewer_name=member.name,
            reviewer_role=member.role,
            decision=decision.value,
            reason=reason,
            snapshot_fingerprint=snapshot_fingerprint,
            decided_at=now,
        )
        self._session.add(decision_model)
        reservation.status = ReviewReservationStatus.CONSUMED.value
        reservation.consumed_at = now
        review.status = _review_status(decision).value
        review.version += 1
        review.updated_at = now
        case_update = self._advance_case_after_decision(
            review,
            decision=decision,
            now=now,
        )
        draft_update = (
            self._publish_approved_response_draft(review, now=now)
            if decision is ReviewDecision.APPROVE
            else {}
        )
        self._set_proposal_state(review, _proposal_state(decision), now=now)
        self._session.add(
            AuditEventModel(
                organization_id=review.organization_id,
                task_id=None,
                run_id=None,
                event_type="case.review_decided",
                actor_type="member",
                actor_id=member.public_id,
                subject_type="review",
                subject_id=review.public_id,
                summary=f"Review decision recorded: {_decision_label(decision)}.",
                data={
                    "decision_id": decision_model.public_id,
                    "decision": decision.value,
                    "snapshot_fingerprint": snapshot_fingerprint,
                    **case_update,
                    **draft_update,
                },
                correlation_id=correlation_id,
                occurred_at=now,
            )
        )
        self._session.flush()
        return self._load_bundle(review, now=now)

    def _publish_approved_response_draft(
        self,
        review: CaseReviewModel,
        *,
        now: datetime,
    ) -> dict[str, object]:
        approved = self._session.scalar(
            select(ProposalResponseDraftModel).where(
                ProposalResponseDraftModel.organization_id == review.organization_id,
                ProposalResponseDraftModel.case_id == review.case_id,
                ProposalResponseDraftModel.proposal_version_id
                == review.proposal_version_id,
            )
        )
        if approved is None or approved.status != "ready":
            raise ReviewSnapshotStale(
                "The reviewed resolution does not contain a ready response draft."
            )
        draft = self._session.scalar(
            select(ResponseDraftModel)
            .where(
                ResponseDraftModel.organization_id == review.organization_id,
                ResponseDraftModel.case_id == review.case_id,
            )
            .with_for_update()
        )
        if draft is None:
            draft = ResponseDraftModel(
                public_id=_stable_public_id("DFT", review.public_id),
                organization_id=review.organization_id,
                case_id=review.case_id,
                subject=approved.subject,
                body=approved.body,
                status="ready",
                version=1,
                updated_at=now,
            )
            self._session.add(draft)
        else:
            draft.subject = approved.subject
            draft.body = approved.body
            draft.status = "ready"
            draft.version += 1
            draft.updated_at = now
        self._session.flush()
        return {
            "response_draft_id": draft.public_id,
            "response_draft_version": draft.version,
        }

    def _advance_case_after_decision(
        self,
        review: CaseReviewModel,
        *,
        decision: ReviewDecision,
        now: datetime,
    ) -> dict[str, object]:
        if decision is ReviewDecision.APPROVE:
            return {}
        case = self._session.scalar(
            select(CaseModel)
            .where(
                CaseModel.id == review.case_id,
                CaseModel.organization_id == review.organization_id,
            )
            .with_for_update()
        )
        if case is None:
            raise ReviewConflict("The reviewed case is no longer available.")
        case.status = "needs_review" if decision is ReviewDecision.ESCALATE else "investigating"
        case.version += 1
        case.updated_at = now
        return {
            "case_status": case.status,
            "case_version": case.version,
        }
