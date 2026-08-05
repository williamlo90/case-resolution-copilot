import type { ReviewSnapshot, ReviewSummary } from "@/domain/reviews/review";

export interface ReviewRepository {
  readonly source: "api" | "mock";
  listReviews(): Promise<readonly ReviewSummary[]>;
  getReviewSnapshot(reviewId: string): Promise<ReviewSnapshot | null>;
}
