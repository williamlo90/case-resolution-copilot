import { getReviewRepository } from "@/data/reviews/review-repository-provider";
import { ReviewQueue } from "@/features/reviews/components/review-queue";
import type { Metadata } from "next";
import { practiceId, openPracticeArea, type PageSearch } from "@/features/practice/data";

export const metadata: Metadata = { title: "Reviews" };
export const dynamic = "force-dynamic";

export default async function ReviewsPage({searchParams}: {searchParams: PageSearch}) {
  const practice = practiceId((await searchParams).practice);
  if (practice) return openPracticeArea(practice, "reviews");
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
