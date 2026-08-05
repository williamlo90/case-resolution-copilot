from app.domain.reviews import (
    ReviewFreshnessRecord,
)
from app.persistence.models import (
    utc_now,
)

from ._base import (
    ReviewRepositoryBase,
)


class ReviewFreshnessRepository(ReviewRepositoryBase):
    def freshness(
        self,
        *,
        organization_public_id: str,
        review_public_id: str,
    ) -> ReviewFreshnessRecord:
        review = self._required_review(organization_public_id, review_public_id)
        return self._freshness(review, now=utc_now())
