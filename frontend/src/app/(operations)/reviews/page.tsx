import { getReviewRepository } from "@/data/reviews/review-repository-provider";
import { ReviewQueue } from "@/features/reviews/components/review-queue";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Reviews" };
export const dynamic = "force-dynamic";

export default async function ReviewsPage() {
  const repository = getReviewRepository();
  const reviews = await repository.listReviews();
  return (
    <ReviewQueue
      reviews={reviews}
      sourceLabel={
        repository.source === "api" ? "Connected review records" : "Sample review data"
      }
    />
  );
}
