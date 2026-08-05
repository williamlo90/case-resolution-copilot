import { reviewSnapshotFixtures, reviewSummaryFixtures } from "@/mocks/fixtures/review-fixtures";
import type { ReviewRepository } from "./review-repository";

export const mockReviewRepository: ReviewRepository = {
  source: "mock",
  async listReviews() { return reviewSummaryFixtures; },
  async getReviewSnapshot(reviewId) { return reviewSnapshotFixtures.find((item) => item.review.id === reviewId) ?? null; },
};
