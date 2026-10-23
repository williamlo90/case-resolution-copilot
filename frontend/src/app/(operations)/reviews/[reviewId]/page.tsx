import { getReviewRepository } from "@/data/reviews/review-repository-provider";
import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { ReviewWorkspace } from "@/features/reviews/components/review-workspace";
import { notFound } from "next/navigation";
import { decideReview, reserveReview } from "../../_actions/reviews";

export const dynamic = "force-dynamic";

export default async function ReviewWorkspacePage({ params }: { params: Promise<{ reviewId: string }> }) {
  const { reviewId } = await params;
  const repository = getReviewRepository();
  const [snapshot, context] = await Promise.all([
    repository.getReviewSnapshot(reviewId),
    getAdministrationRepository().getSessionContext(),
  ]);
  if (!snapshot) notFound();
  const connected = repository.source === "api";
  const canReserve = context.actor.permissions.includes("review:reserve");
  const canDecide = context.actor.permissions.includes("review:decide");
  return (
    <ReviewWorkspace
      snapshot={snapshot}
      reserveAction={
        connected && canReserve
          ? reserveReview.bind(null, reviewId, snapshot.review.version)
          : undefined
      }
      decideAction={
        connected && canDecide
          ? decideReview.bind(
              null,
              reviewId,
              snapshot.review.version,
              snapshot.review.snapshotFingerprint,
            )
          : undefined
      }
    />
  );
}
