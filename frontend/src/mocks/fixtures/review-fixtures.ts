import { ReviewSnapshotSchema, ReviewSummarySchema, type ReviewSnapshot, type ReviewSummary } from "@/domain/reviews/review";
import { caseWorkspaceFixtures } from "./case-fixtures";

const rawReviews = [
  {
    id: "RV-5001", caseId: "CS-2048", proposal: { id: "PROP-2048-1", version: 1, outcome: "Reverse duplicate charge" }, impact: { amount: 99, currency: "USD" },
    reviewReason: "Financial impact exceeds the specialist approval limit.", policyState: "supported", uncertainty: "medium",
    submittedBy: { id: "USR-AR", name: "Alex Rivera" }, submittedAt: "2026-07-21T03:28:00.000Z", waitingMinutes: 52,
    snapshotFreshness: { status: "current", checkedAt: "2026-07-21T03:27:00.000Z", reason: null }, status: "pending", reservation: null,
  },
  {
    id: "RV-5000", caseId: "CS-2042", proposal: { id: "PROP-2042-1", version: 1, outcome: "Escalate for verified account recovery" }, impact: null,
    reviewReason: "VIP account recovery requires supervisor authority.", policyState: "supported", uncertainty: "low",
    submittedBy: { id: "USR-PS", name: "Priya Shah" }, submittedAt: "2026-07-21T02:11:00.000Z", waitingMinutes: 129,
    snapshotFreshness: { status: "stale", checkedAt: "2026-07-21T02:10:00.000Z", reason: "Account context changed after this proposal was submitted." }, status: "reserved",
    reservation: { reviewerId: "USR-ST", reviewerName: "Sofia Torres", reservedAt: "2026-07-21T03:41:00.000Z", expiresAt: "2026-07-21T04:11:00.000Z" },
  },
  {
    id: "RV-4999", caseId: "CS-2045", proposal: { id: "PROP-2045-1", version: 1, outcome: "Prepare service exception resolution" }, impact: { amount: 78, currency: "USD" },
    reviewReason: "Service exception requires a documented business decision.", policyState: "possible_conflict", uncertainty: "high",
    submittedBy: { id: "USR-JM", name: "Jordan Miles" }, submittedAt: "2026-07-21T01:54:00.000Z", waitingMinutes: 146,
    snapshotFreshness: { status: "current", checkedAt: "2026-07-21T03:25:00.000Z", reason: null }, status: "pending", reservation: null,
  },
] as const;

export const reviewSummaryFixtures: readonly ReviewSummary[] = ReviewSummarySchema.array().parse(rawReviews);

export const reviewSnapshotFixtures: readonly ReviewSnapshot[] = reviewSummaryFixtures.map((review) => {
  const workspace = caseWorkspaceFixtures.find((item) => item.case.id === review.caseId) ?? caseWorkspaceFixtures[0];
  return ReviewSnapshotSchema.parse({
    review,
    caseVersion: `${review.caseId}-v4`,
    contextVersion: "CTX-2026-07-21.1",
    riskRuleVersion: "RISK-3.4",
    facts: workspace.facts,
    businessContexts: workspace.businessContexts,
    evidence: review.policyState === "possible_conflict" ? workspace.evidence.map((item, index) => index === 0 ? { ...item, conflictState: "possible" } : item) : workspace.evidence,
    risks: workspace.risks,
    proposal: { ...workspace.proposal, id: review.proposal.id, version: review.proposal.version, outcome: review.proposal.outcome, impact: review.impact, state: "under_review" },
    actions: workspace.proposedActions.map((item) => ({ ...item, impact: review.impact })),
    approvalRule: {
      id: "RULE-FIN-50",
      name: "Supervisor review for consequential changes",
      explanation: review.reviewReason,
      requiredRole: "Support supervisor",
    },
    availableDecisions: review.snapshotFreshness.status === "stale" || review.reservation?.reviewerId !== undefined
      ? []
      : ["approve", "request_changes", "reject", "escalate"],
    decisionHistory: [],
  });
});

export const primaryReviewSnapshotFixture = reviewSnapshotFixtures[0];
