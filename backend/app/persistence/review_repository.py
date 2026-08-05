from app.persistence.reviews.freshness import ReviewFreshnessRepository
from app.persistence.reviews.legacy import LegacyReviewRepository
from app.persistence.reviews.queries import ReviewQueryRepository
from app.persistence.reviews.workflow import ReviewWorkflowRepository


class ReviewRepository(
    ReviewQueryRepository,
    ReviewWorkflowRepository,
    LegacyReviewRepository,
    ReviewFreshnessRepository,
):
    """Facade preserving the public review persistence contract."""
