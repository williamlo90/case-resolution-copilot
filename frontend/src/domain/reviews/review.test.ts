import { reviewSnapshotFixtures, reviewSummaryFixtures } from "@/mocks/fixtures/review-fixtures";
import { describe, expect, it } from "vitest";
import { ReviewSnapshotSchema, ReviewSummarySchema } from "./review";

describe("review contract", () => {
  it("binds every review to a proposal and case snapshot", () => {
    expect(ReviewSummarySchema.array().parse(reviewSummaryFixtures)).toHaveLength(3);
    const snapshot = ReviewSnapshotSchema.parse(reviewSnapshotFixtures[0]);
    expect(snapshot.review.proposal.id).toBe(snapshot.proposal.id);
    expect(snapshot.caseVersion).toBeTruthy();
  });

  it("does not offer decisions for stale snapshots", () => {
    const stale = ReviewSnapshotSchema.parse(reviewSnapshotFixtures[1]);
    expect(stale.review.snapshotFreshness.status).toBe("stale");
    expect(stale.availableDecisions).toEqual([]);
  });
});
