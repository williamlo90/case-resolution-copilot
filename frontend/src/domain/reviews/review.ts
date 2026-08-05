import {
  CaseProposalSchema,
  CaseWorkspaceSchema,
  MoneySchema,
  PublicCaseIdSchema,
} from "@/domain/cases/case";
import { z } from "zod";

export const ReviewStatusSchema = z.enum([
  "pending",
  "reserved",
  "approved",
  "changes_requested",
  "rejected",
  "escalated",
]);

export const ReviewDecisionSchema = z.enum(["approve", "request_changes", "reject", "escalate"]);

export const ReviewSummarySchema = z.object({
  id: z.string().regex(/^RV-[A-Z0-9-]+$/),
  caseId: PublicCaseIdSchema,
  proposal: z.object({ id: z.string().min(1), version: z.number().int().positive(), outcome: z.string().min(1) }),
  impact: MoneySchema.nullable(),
  reviewReason: z.string().min(1),
  policyState: z.enum(["supported", "possible_conflict", "missing"]),
  uncertainty: z.enum(["low", "medium", "high"]),
  submittedBy: z.object({ id: z.string().min(1), name: z.string().min(1) }),
  submittedAt: z.string().datetime(),
  waitingMinutes: z.number().int().nonnegative(),
  snapshotFreshness: z.object({
    status: z.enum(["current", "stale"]),
    checkedAt: z.string().datetime(),
    reason: z.string().min(1).nullable(),
  }),
  status: ReviewStatusSchema,
  reservation: z.object({
    reviewerId: z.string().min(1),
    reviewerName: z.string().min(1),
    reservedAt: z.string().datetime(),
    expiresAt: z.string().datetime(),
  }).nullable(),
  snapshotFingerprint: z.string().length(64).default("0".repeat(64)),
  version: z.number().int().positive().default(1),
});

export const ReviewSnapshotSchema = z.object({
  review: ReviewSummarySchema,
  caseVersion: z.string().min(1),
  contextVersion: z.string().min(1),
  riskRuleVersion: z.string().min(1),
  facts: CaseWorkspaceSchema.shape.facts,
  businessContexts: CaseWorkspaceSchema.shape.businessContexts,
  evidence: CaseWorkspaceSchema.shape.evidence,
  risks: CaseWorkspaceSchema.shape.risks,
  proposal: CaseProposalSchema,
  actions: CaseWorkspaceSchema.shape.proposedActions,
  approvalRule: z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    explanation: z.string().min(1),
    requiredRole: z.string().min(1),
    version: z.number().int().positive().default(1),
  }),
  availableDecisions: z.array(ReviewDecisionSchema),
  decisionHistory: z.array(z.object({
    id: z.string().min(1),
    decision: ReviewDecisionSchema,
    reason: z.string().min(1),
    actor: z.string().min(1),
    decidedAt: z.string().datetime(),
  })),
});

export type ReviewStatus = z.infer<typeof ReviewStatusSchema>;
export type ReviewDecision = z.infer<typeof ReviewDecisionSchema>;
export type ReviewSummary = z.infer<typeof ReviewSummarySchema>;
export type ReviewSnapshot = z.infer<typeof ReviewSnapshotSchema>;
