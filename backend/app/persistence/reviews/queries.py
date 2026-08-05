from sqlalchemy import and_, func, or_, select

from app.domain.reviews import (
    ReviewBundleRecord,
    ReviewPageRecord,
    ReviewQueueItemRecord,
)
from app.persistence.models import (
    CaseModel,
    CaseProposalModel,
    CaseProposalVersionModel,
    CaseReviewModel,
    OrganizationModel,
    utc_now,
)

from ._base import (
    ReviewRepositoryBase,
    _decode_cursor,
    _encode_cursor,
    _hash,
)


class ReviewQueryRepository(ReviewRepositoryBase):
    def get_for_proposal(
        self,
        *,
        organization_public_id: str,
        case_public_id: str,
        proposal_version: int,
    ) -> ReviewBundleRecord | None:
        scoped = self._scoped_case(organization_public_id, case_public_id)
        if scoped is None:
            return None
        _, case = scoped
        version = self._session.scalar(
            select(CaseProposalVersionModel).where(
                CaseProposalVersionModel.organization_id == case.organization_id,
                CaseProposalVersionModel.case_id == case.id,
                CaseProposalVersionModel.version == proposal_version,
            )
        )
        if version is None:
            return None
        review = self._session.scalar(
            select(CaseReviewModel).where(
                CaseReviewModel.organization_id == case.organization_id,
                CaseReviewModel.case_id == case.id,
                CaseReviewModel.proposal_version_id == version.id,
            )
        )
        if review is None:
            return None
        self._reconcile_expired(review=review, now=utc_now())
        return self._load_bundle(review, now=utc_now())

    def get(
        self, *, organization_public_id: str, review_public_id: str
    ) -> ReviewBundleRecord | None:
        review = self._scoped_review(organization_public_id, review_public_id)
        if review is None:
            return None
        now = utc_now()
        self._reconcile_expired(review=review, now=now)
        return self._load_bundle(review, now=now)

    def list(
        self,
        *,
        organization_public_id: str,
        status: str | None,
        policy_state: str | None,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> ReviewPageRecord:
        organization = self._session.scalar(
            select(OrganizationModel).where(OrganizationModel.public_id == organization_public_id)
        )
        if organization is None:
            return ReviewPageRecord(items=[], next_cursor=None, total=0)
        now = utc_now()
        self._reconcile_expired(organization_id=organization.id, now=now)
        filters = [
            CaseReviewModel.organization_id == organization.id,
        ]
        normalized_query = query.strip().lower() if query else None
        if status:
            filters.append(CaseReviewModel.status == status)
        if policy_state:
            filters.append(CaseReviewModel.policy_state == policy_state)
        if normalized_query:
            pattern = f"%{normalized_query}%"
            filters.append(
                or_(
                    func.lower(CaseReviewModel.public_id).like(pattern),
                    func.lower(CaseReviewModel.review_reason).like(pattern),
                    func.lower(CaseReviewModel.submitted_by_name).like(pattern),
                    func.lower(CaseProposalVersionModel.outcome).like(pattern),
                    func.lower(CaseModel.public_id).like(pattern),
                )
            )
        total_filters = list(filters)
        filter_fingerprint = _hash(
            {
                "organization": organization_public_id,
                "status": status,
                "policy_state": policy_state,
                "query": normalized_query,
            }
        )
        cursor_values = _decode_cursor(cursor, filter_fingerprint) if cursor else None
        if cursor_values is not None:
            cursor_time, cursor_id = cursor_values
            filters.append(
                or_(
                    CaseReviewModel.submitted_at < cursor_time,
                    and_(
                        CaseReviewModel.submitted_at == cursor_time,
                        CaseReviewModel.public_id > cursor_id,
                    ),
                )
            )
        base = (
            select(CaseReviewModel, CaseProposalModel, CaseProposalVersionModel)
            .join(CaseModel, CaseModel.id == CaseReviewModel.case_id)
            .join(CaseProposalModel, CaseProposalModel.id == CaseReviewModel.proposal_id)
            .join(
                CaseProposalVersionModel,
                CaseProposalVersionModel.id == CaseReviewModel.proposal_version_id,
            )
            .where(*filters)
        )
        rows = self._session.execute(
            base.order_by(
                CaseReviewModel.submitted_at.desc(),
                CaseReviewModel.public_id,
            ).limit(limit + 1)
        ).all()
        visible = rows[:limit]
        items = [
            ReviewQueueItemRecord(
                bundle=self._load_bundle(review, now=now),
                proposal_public_id=proposal.public_id,
                proposal_outcome=version.outcome,
                freshness=self._freshness(review, now=now),
            )
            for review, proposal, version in visible
        ]
        next_cursor = None
        if len(rows) > limit and visible:
            last_review = visible[-1][0]
            next_cursor = _encode_cursor(
                last_review.submitted_at,
                last_review.public_id,
                filter_fingerprint,
            )
        total = self._session.scalar(
            select(func.count(CaseReviewModel.id))
            .select_from(CaseReviewModel)
            .join(CaseModel, CaseModel.id == CaseReviewModel.case_id)
            .join(
                CaseProposalVersionModel,
                CaseProposalVersionModel.id == CaseReviewModel.proposal_version_id,
            )
            .where(*total_filters)
        )
        return ReviewPageRecord(
            items=items,
            next_cursor=next_cursor,
            total=total or 0,
        )
