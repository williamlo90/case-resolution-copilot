import { apiMoneySchema, apiRequest, isApiNotFound } from "@/data/api/api-client";
import {
  ActionDetailSchema,
  ActionSummarySchema,
  type ActionDetail,
  type ActionSummary,
} from "@/domain/actions/action";
import { z } from "zod";
import type { ActionRepository } from "./action-repository";

const apiActorSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
});

const apiActionSummarySchema = z.object({
  id: z.string().min(1),
  case_id: z.string().min(1),
  type: z.string().min(1),
  label: z.string().min(1),
  target: z.string().min(1),
  impact: apiMoneySchema.nullable(),
  status: z.enum([
    "ready",
    "running",
    "completed",
    "failed_safe",
    "outcome_unknown",
    "recovery_required",
  ]),
  execution_blocker: z
    .enum([
      "permission",
      "duplicate",
      "expired_approval",
      "connection_unavailable",
      "stale_proposal",
    ])
    .nullable(),
  attempt_count: z.number().int().nonnegative(),
  owner: apiActorSchema.nullable(),
  updated_at: z.string().datetime(),
  recovery_required: z.boolean(),
  version: z.number().int().positive(),
});

const apiActionDetailSchema = z.object({
  action: apiActionSummarySchema,
  approved_proposal: z.object({
    id: z.string().min(1),
    version: z.number().int().positive(),
    review_id: z.string().min(1),
    approved_at: z.string().datetime(),
  }),
  authority: z.object({
    actor: apiActorSchema,
    role: z.string().min(1),
    rule: z.string().min(1),
  }),
  typed_parameters: z.record(z.string(), z.string()),
  target_connection: z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    environment: z.enum(["demo", "sandbox", "production"]),
    health: z.enum(["healthy", "degraded", "unavailable", "not_configured"]),
    last_checked_at: z.string().datetime().nullable(),
  }),
  idempotency_key: z.string().min(1),
  attempts: z.array(
    z.object({
      id: z.string().min(1),
      number: z.number().int().positive(),
      started_at: z.string().datetime(),
      finished_at: z.string().datetime().nullable(),
      actor: apiActorSchema,
      outcome: z.enum([
        "running",
        "succeeded",
        "failed_before_change",
        "unknown",
      ]),
      detail: z.string().min(1),
    }),
  ),
  receipt: z
    .object({
      id: z.string().min(1),
      external_reference: z.string().min(1),
      recorded_at: z.string().datetime(),
    })
    .nullable(),
  expected_outcome: z.string().min(1),
  observed_outcome: z.string().nullable(),
  execution_blocker: z
    .enum([
      "permission",
      "duplicate",
      "expired_approval",
      "connection_unavailable",
      "stale_proposal",
    ])
    .nullable(),
  available_commands: z.array(
    z.enum([
      "execute",
      "retry_safe",
      "reconcile",
      "record_manual_outcome",
      "escalate",
    ]),
  ),
});

const actionListEnvelopeSchema = z.object({
  items: z.array(apiActionSummarySchema),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
});

const actionDetailEnvelopeSchema = z.object({ data: apiActionDetailSchema });

function mapSummary(raw: z.infer<typeof apiActionSummarySchema>): ActionSummary {
  return ActionSummarySchema.parse({
    id: raw.id,
    caseId: raw.case_id,
    type: raw.type,
    label: raw.label,
    target: raw.target,
    impact: raw.impact,
    status: raw.status,
    executionBlocker: raw.execution_blocker,
    attemptCount: raw.attempt_count,
    owner: raw.owner,
    updatedAt: raw.updated_at,
    recoveryRequired: raw.recovery_required,
    version: raw.version,
  });
}

function mapDetail(raw: z.infer<typeof apiActionDetailSchema>): ActionDetail {
  return ActionDetailSchema.parse({
    action: mapSummary(raw.action),
    approvedProposal: {
      id: raw.approved_proposal.id,
      version: raw.approved_proposal.version,
      reviewId: raw.approved_proposal.review_id,
      approvedAt: raw.approved_proposal.approved_at,
    },
    authority: {
      actor: raw.authority.actor.name,
      role: raw.authority.role,
      rule: raw.authority.rule,
    },
    typedParameters: raw.typed_parameters,
    targetConnection: {
      id: raw.target_connection.id,
      name: raw.target_connection.name,
      environment: raw.target_connection.environment,
      health: raw.target_connection.health,
      lastCheckedAt: raw.target_connection.last_checked_at,
    },
    idempotencyKey: raw.idempotency_key,
    attempts: raw.attempts.map((item) => ({
      id: item.id,
      number: item.number,
      startedAt: item.started_at,
      finishedAt: item.finished_at,
      actor: item.actor.name,
      outcome: item.outcome,
      detail: item.detail,
    })),
    receipt: raw.receipt
      ? {
          id: raw.receipt.id,
          externalReference: raw.receipt.external_reference,
          recordedAt: raw.receipt.recorded_at,
        }
      : null,
    expectedOutcome: raw.expected_outcome,
    observedOutcome: raw.observed_outcome,
    executionBlocker: raw.execution_blocker,
    availableCommands: raw.available_commands,
  });
}

export const apiActionRepository: ActionRepository = {
  source: "api",
  async listActions() {
    const envelope = await apiRequest(
      "/api/actions?limit=100",
      actionListEnvelopeSchema,
    );
    return envelope.items.map(mapSummary);
  },
  async getActionDetail(actionId) {
    try {
      const envelope = await apiRequest(
        `/api/actions/${encodeURIComponent(actionId)}`,
        actionDetailEnvelopeSchema,
      );
      return mapDetail(envelope.data);
    } catch (error) {
      if (isApiNotFound(error)) return null;
      throw error;
    }
  },
};
