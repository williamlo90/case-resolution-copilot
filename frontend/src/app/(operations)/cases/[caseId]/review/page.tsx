import { getReviewRepository } from "@/data/reviews/review-repository-provider";
import { notFound, redirect } from "next/navigation";

export default async function LegacyCaseReviewPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  const reviews = await getReviewRepository().listReviews();
  const review = reviews.find((item) => item.caseId === caseId);
  if (!review) notFound();
  redirect(`/reviews/${review.id}`);
}
