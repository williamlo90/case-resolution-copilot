import { MoneySchema, PublicCaseIdSchema } from "@/domain/cases/case";
import { z } from "zod";

export const ActionStatusSchema = z.enum([
  "ready",
  "running",
  "completed",
  "failed_safe",
  "outcome_unknown",
  "recovery_required",
]);

export const ActionExecutionBlockerSchema = z.enum([
  "permission",
  "duplicate",
  "expired_approval",
  "connection_unavailable",
  "stale_proposal",
]);

export const ActionConnectionHealthSchema = z.enum([
  "healthy",
  "degraded",
  "unavailable",
  "not_configured",
]);

export const ActionSummarySchema = z.object({
  id: z.string().regex(/^AC-[A-Z0-9-]+$/),
  caseId: PublicCaseIdSchema,
  type: z.string().min(1),
  label: z.string().min(1),
  target: z.string().min(1),
  impact: MoneySchema.nullable(),
  status: ActionStatusSchema,
  executionBlocker: ActionExecutionBlockerSchema.nullable().default(null),
  attemptCount: z.number().int().nonnegative(),
  owner: z.object({ id: z.string().min(1), name: z.string().min(1) }).nullable(),
  updatedAt: z.string().datetime(),
  recoveryRequired: z.boolean(),
  version: z.number().int().positive().default(1),
});

export const ActionDetailSchema = z.object({
  action: ActionSummarySchema,
  approvedProposal: z.object({ id: z.string().min(1), version: z.number().int().positive(), reviewId: z.string().min(1), approvedAt: z.string().datetime() }),
  authority: z.object({ actor: z.string().min(1), role: z.string().min(1), rule: z.string().min(1) }),
  typedParameters: z.record(z.string(), z.string()),
  targetConnection: z.object({ id: z.string().min(1), name: z.string().min(1), environment: z.enum(["demo", "sandbox", "production"]), health: ActionConnectionHealthSchema, lastCheckedAt: z.string().datetime().nullable() }),
  idempotencyKey: z.string().min(1),
  attempts: z.array(z.object({ id: z.string().min(1), number: z.number().int().positive(), startedAt: z.string().datetime(), finishedAt: z.string().datetime().nullable(), actor: z.string().min(1), outcome: z.enum(["running", "succeeded", "failed_before_change", "unknown"]), detail: z.string().min(1) })),
  receipt: z.object({ id: z.string().min(1), externalReference: z.string().min(1), recordedAt: z.string().datetime() }).nullable(),
  expectedOutcome: z.string().min(1),
  observedOutcome: z.string().min(1).nullable(),
  executionBlocker: ActionExecutionBlockerSchema.nullable(),
  availableCommands: z.array(z.enum(["execute", "retry_safe", "reconcile", "record_manual_outcome", "escalate"])),
});

export type ActionStatus = z.infer<typeof ActionStatusSchema>;
export type ActionSummary = z.infer<typeof ActionSummarySchema>;
export type ActionDetail = z.infer<typeof ActionDetailSchema>;
