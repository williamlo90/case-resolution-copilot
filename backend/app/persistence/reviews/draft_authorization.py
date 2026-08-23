from hashlib import sha256

from sqlalchemy import select

from app.domain.inbox import ReviewDraftAuthorization
from app.domain.reviews import ReviewFreshness, ReviewSnapshotStale
from app.persistence.models import (
    CaseModel,
    CaseReviewDecisionModel,
    CaseReviewModel,
    OrganizationModel,
    utc_now,
)

from ._base import ReviewRepositoryBase


class ReviewDraftAuthorizationReader(ReviewRepositoryBase):
    def current_approval(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
    ) -> ReviewDraftAuthorization:
        review = self._session.scalar(
            select(CaseReviewModel)
            .join(OrganizationModel, OrganizationModel.id == CaseReviewModel.organization_id)
            .join(
                CaseModel,
                (CaseModel.organization_id == CaseReviewModel.organization_id)
                & (CaseModel.id == CaseReviewModel.case_id),
            )
            .where(
                OrganizationModel.public_id == organization_public_id,
                CaseModel.public_id == case_public_id,
                CaseReviewModel.status == "approved",
            )
            .order_by(CaseReviewModel.submitted_at.desc())
            .limit(1)
        )
        if review is None:
            raise ReviewSnapshotStale("Complete the required review before creating a draft.")
        snapshot = self._required_snapshot(review)
        decision = self._session.scalar(
            select(CaseReviewDecisionModel).where(
                CaseReviewDecisionModel.organization_id == review.organization_id,
                CaseReviewDecisionModel.case_id == review.case_id,
                CaseReviewDecisionModel.review_id == review.id,
                CaseReviewDecisionModel.decision == "approve",
                CaseReviewDecisionModel.snapshot_fingerprint
                == snapshot.snapshot_fingerprint,
            )
        )
        freshness = self._freshness(review, now=utc_now())
        if (
            decision is None
            or freshness.status is ReviewFreshness.STALE
            or not snapshot.execution_eligible
        ):
            raise ReviewSnapshotStale(
                freshness.reason
                or "The approved review no longer matches the current case."
            )
        policy_fingerprint = sha256(
            "\0".join(
                [
                    snapshot.evidence_fingerprint,
                    snapshot.risk_fingerprint,
                    snapshot.risk_rule_version,
                ]
            ).encode("utf-8")
        ).hexdigest()
        return ReviewDraftAuthorization(
            review_id=review.id,
            snapshot_fingerprint=snapshot.snapshot_fingerprint,
            evidence_fingerprint=snapshot.evidence_fingerprint,
            policy_fingerprint=policy_fingerprint,
        )
