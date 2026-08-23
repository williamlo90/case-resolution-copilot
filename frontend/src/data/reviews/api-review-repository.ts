import { apiMoneySchema, apiRequest, isApiNotFound } from "@/data/api/api-client";
import {
  ReviewSnapshotSchema,
  ReviewSummarySchema,
  type ReviewSnapshot,
  type ReviewSummary,
} from "@/domain/reviews/review";
import { z } from "zod";
import type { ReviewRepository } from "./review-repository";

const apiActorSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
});

const apiReviewSummarySchema = z.object({
  id: z.string().min(1),
  case_id: z.string().min(1),
  proposal: z.object({
    id: z.string().min(1),
    version: z.number().int().positive(),
    outcome: z.string().min(1),
  }),
  impact: apiMoneySchema.nullable(),
  review_reason: z.string().min(1),
  policy_state: z.enum(["supported", "possible_conflict", "missing"]),
  uncertainty: z.enum(["low", "medium", "high"]),
  submitted_by: apiActorSchema,
  submitted_at: z.string().datetime(),
  waiting_minutes: z.number().int().nonnegative(),
  snapshot_freshness: z.object({
    status: z.enum(["current", "stale"]),
    checked_at: z.string().datetime(),
    reason: z.string().nullable(),
  }),
  snapshot_fingerprint: z.string().length(64),
  status: z.enum([
    "pending",
    "reserved",
    "approved",
    "changes_requested",
    "rejected",
    "escalated",
  ]),
  reservation: z
    .object({
      reviewer: apiActorSchema,
      reserved_at: z.string().datetime(),
      expires_at: z.string().datetime(),
    })
    .nullable(),
  version: z.number().int().positive(),
});

const apiBusinessContextSchema = z.object({
  id: z.string().min(1),
  type: z.enum([
    "invoice",
    "payment",
    "subscription",
    "account",
    "order",
    "delivery",
    "other",
  ]),
  label: z.string().min(1),
  source: z.string().min(1),
  source_reference: z.string().min(1),
  status: z.string().min(1),
  fields: z.record(z.string(), z.string()),
  captured_at: z.string().datetime(),
  source_freshness: z.object({
    status: z.enum(["current", "stale", "unavailable"]),
    checked_at: z.string().datetime().nullable(),
  }),
  version: z.number().int().positive(),
});

const apiEvidenceSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  citation: z.string().min(1),
  excerpt: z.string().min(1),
  applicability: z.string().min(1),
  effective_date: z.string().min(1),
  freshness: z.enum(["current", "stale"]),
  conflict_state: z.enum(["none", "possible", "confirmed"]),
});

const apiProposalSchema = z.object({
  id: z.string().min(1),
  version: z.number().int().positive(),
  outcome: z.string().min(1),
  impact: apiMoneySchema.nullable(),
  confidence: z.enum(["high", "medium", "low"]),
  uncertainty: z.string().min(1),
  rationale: z.string().min(1),
  state: z.enum([
    "draft",
    "information_needed",
    "ready_for_review",
    "under_review",
    "approved",
    "rejected",
  ]),
});

const apiReviewSnapshotSchema = z.object({
  review: apiReviewSummarySchema,
  case_version: z.number().int().positive(),
  context_fingerprint: z.string().min(1),
  risk_rule_version: z.string().min(1),
  facts: z.array(
    z.object({
      id: z.string().min(1),
      statement: z.string().min(1),
      source: z.string().min(1),
      verified_at: z.string().datetime(),
    }),
  ),
  business_contexts: z.array(apiBusinessContextSchema),
  evidence: z.array(apiEvidenceSchema),
  risks: z.array(
    z.object({
      id: z.string().min(1),
      label: z.string().min(1),
      outcome: z.enum([
        "passed",
        "requires_review",
        "information_needed",
        "blocked",
      ]),
      explanation: z.string().min(1),
    }),
  ),
  proposal: apiProposalSchema,
  actions: z.array(
    z.object({
      id: z.string().min(1),
      type: z.string().min(1),
      label: z.string().min(1),
      impact: apiMoneySchema.nullable(),
      expected_outcome: z.string().min(1),
      review_required: z.boolean(),
    }),
  ),
  approval_rule: z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    explanation: z.string().min(1),
    required_role: z.string().min(1),
    version: z.number().int().positive(),
  }),
  available_decisions: z.array(
    z.enum(["approve", "request_changes", "reject", "escalate"]),
  ),
  decision_history: z.array(
    z.object({
      id: z.string().min(1),
      decision: z.enum([
        "approve",
        "request_changes",
        "reject",
        "escalate",
      ]),
      reason: z.string().min(1),
      actor: apiActorSchema,
      decided_at: z.string().datetime(),
    }),
  ),
});

const reviewListEnvelopeSchema = z.object({
  items: z.array(apiReviewSummarySchema),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
});

const reviewDetailEnvelopeSchema = z.object({ data: apiReviewSnapshotSchema });

function mapSummary(raw: z.infer<typeof apiReviewSummarySchema>): ReviewSummary {
  return ReviewSummarySchema.parse({
    id: raw.id,
    caseId: raw.case_id,
    proposal: raw.proposal,
    impact: raw.impact,
    reviewReason: raw.review_reason,
    policyState: raw.policy_state,
    uncertainty: raw.uncertainty,
    submittedBy: raw.submitted_by,
    submittedAt: raw.submitted_at,
    waitingMinutes: raw.waiting_minutes,
    snapshotFreshness: {
      status: raw.snapshot_freshness.status,
      checkedAt: raw.snapshot_freshness.checked_at,
      reason: raw.snapshot_freshness.reason,
    },
    status: raw.status,
    reservation: raw.reservation
      ? {
          reviewerId: raw.reservation.reviewer.id,
          reviewerName: raw.reservation.reviewer.name,
          reservedAt: raw.reservation.reserved_at,
          expiresAt: raw.reservation.expires_at,
        }
      : null,
    snapshotFingerprint: raw.snapshot_fingerprint,
    version: raw.version,
  });
}

function mapSnapshot(
  raw: z.infer<typeof apiReviewSnapshotSchema>,
): ReviewSnapshot {
  return ReviewSnapshotSchema.parse({
    review: mapSummary(raw.review),
    caseVersion: String(raw.case_version),
    contextVersion: raw.context_fingerprint,
    riskRuleVersion: raw.risk_rule_version,
    facts: raw.facts.map((item) => ({
      id: item.id,
      statement: item.statement,
      source: item.source,
      verifiedAt: item.verified_at,
    })),
    businessContexts: raw.business_contexts.map((context) => ({
      id: context.id,
      type: context.type,
      label: context.label,
      source: context.source,
      sourceReference: context.source_reference,
      status: context.status,
      fields: context.fields,
      capturedAt: context.captured_at,
      sourceFreshness: {
        status: context.source_freshness.status,
        checkedAt: context.source_freshness.checked_at,
      },
      version: context.version,
    })),
    evidence: raw.evidence.map((item) => ({
      id: item.id,
      title: item.title,
      citation: item.citation,
      excerpt: item.excerpt,
      applicability: item.applicability,
      effectiveDate: item.effective_date,
      freshness: item.freshness,
      conflictState: item.conflict_state,
    })),
    risks: raw.risks,
    proposal: raw.proposal,
    actions: raw.actions.map((item) => ({
      id: item.id,
      type: item.type,
      label: item.label,
      impact: item.impact,
      expectedOutcome: item.expected_outcome,
      reviewRequired: item.review_required,
    })),
    approvalRule: {
      id: raw.approval_rule.id,
      name: raw.approval_rule.name,
      explanation: raw.approval_rule.explanation,
      requiredRole: raw.approval_rule.required_role,
      version: raw.approval_rule.version,
    },
    availableDecisions: raw.available_decisions,
    decisionHistory: raw.decision_history.map((item) => ({
      id: item.id,
      decision: item.decision,
      reason: item.reason,
      actor: item.actor.name,
      decidedAt: item.decided_at,
    })),
  });
}

export const apiReviewRepository: ReviewRepository = {
  source: "api",
  async listReviews() {
    const envelope = await apiRequest(
      "/api/reviews?limit=100",
      reviewListEnvelopeSchema,
    );
    return envelope.items.map(mapSummary);
  },
  async getReviewSnapshot(reviewId) {
    try {
      const envelope = await apiRequest(
        `/api/reviews/${encodeURIComponent(reviewId)}`,
        reviewDetailEnvelopeSchema,
      );
      return mapSnapshot(envelope.data);
    } catch (error) {
      if (isApiNotFound(error)) return null;
      throw error;
    }
  },
};
