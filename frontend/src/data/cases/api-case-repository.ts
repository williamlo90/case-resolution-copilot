import { apiMoneySchema, apiRequest, isApiNotFound } from "@/data/api/api-client";
import {
  CaseSummarySchema,
  CaseWorkspaceSchema,
  type CaseActivity,
  type CaseCollectionWindow,
  type CaseConversationMessage,
  type CaseSummary,
  type CaseWorkspace,
} from "@/domain/cases/case";
import { z } from "zod";
import {
  CASE_QUEUE_PAGE_SIZE,
  type CaseListOptions,
  type CaseRepository,
} from "./case-repository";

const apiCaseSummarySchema = z.object({
  id: z.string().min(1),
  source_id: z.string().min(1),
  external_reference: z.string().min(1),
  category: z.enum([
    "billing_dispute",
    "refund_request",
    "account_access",
    "service_exception",
  ]),
  issue: z.string().min(1),
  customer: z.object({
    name: z.string().min(1),
    is_vip: z.boolean(),
  }),
  status: z.enum([
    "new",
    "investigating",
    "information_needed",
    "needs_review",
    "waiting_customer",
    "in_progress",
    "completed",
  ]),
  owner: z
    .object({
      id: z.string().min(1),
      name: z.string().min(1),
      initials: z.string().min(1),
    })
    .nullable(),
  urgency: z.enum(["low", "medium", "high", "critical"]),
  risk: z.enum(["low", "medium", "high"]),
  sla_minutes_remaining: z.number().int().nonnegative(),
  updated_at: z.string().datetime().nullable(),
  source_freshness: z.object({
    status: z.enum(["current", "stale", "unavailable"]),
    checked_at: z.string().datetime().nullable(),
  }),
  impact: apiMoneySchema.nullable(),
  version: z.number().int().positive(),
});

export const apiConversationMessageSchema = z.object({
  id: z.string().min(1),
  organization_id: z.string().min(1),
  case_id: z.string().min(1),
  author_type: z.enum(["customer", "member", "service", "system"]),
  author_id: z.string().min(1).nullable(),
  author_name: z.string().min(1),
  channel: z.enum(["email", "chat", "phone", "webhook", "internal_note"]),
  body: z.string().min(1),
  internal: z.boolean(),
  source_reference: z.string().min(1).nullable(),
  created_at: z.string().datetime(),
  version: z.number().int().positive(),
});

export const apiCaseActivitySchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  detail: z.string().min(1),
  actor: z.string().min(1),
  timestamp: z.string().datetime(),
  status: z.enum(["completed", "current", "waiting", "failed"]),
});

const apiCollectionWindowSchema = z.object({
  returned: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
  has_more: z.boolean(),
  next_cursor: z.string().min(1).nullable(),
});

const apiCaseWorkspaceSchema = z.object({
  case: apiCaseSummarySchema,
  request: z.object({
    received_at: z.string().datetime(),
    channel: z.enum(["email", "chat", "phone", "webhook"]),
    customer_message: z.string().min(1),
    summary: z.string().min(1),
  }),
  conversation: z.object({
    id: z.string().min(1),
    organization_id: z.string().min(1),
    case_id: z.string().min(1),
    messages: z.array(apiConversationMessageSchema),
    version: z.number().int().positive(),
    updated_at: z.string().datetime(),
  }),
  customer: z.object({
    id: z.string().min(1),
    tier: z.enum(["standard", "vip", "enterprise"]),
    locale: z.string().min(1),
    contact: z.string().min(1),
  }),
  business_contexts: z.array(
    z.object({
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
      status: z.string().min(1),
      fields: z.record(z.string(), z.string()),
    }),
  ),
  facts: z.array(
    z.object({
      id: z.string().min(1),
      statement: z.string().min(1),
      source: z.string().min(1),
      verified_at: z.string().datetime(),
    }),
  ),
  missing_information: z.array(
    z.object({
      id: z.string().min(1),
      label: z.string().min(1),
      description: z.string().min(1),
      blocking: z.boolean(),
    }),
  ),
  evidence: z.array(
    z.object({
      id: z.string().min(1),
      title: z.string().min(1),
      citation: z.string().min(1),
      excerpt: z.string().min(1),
      applicability: z.string().min(1),
      effective_date: z.string().min(1),
      freshness: z.enum(["current", "stale"]),
      conflict_state: z.enum(["none", "possible", "confirmed"]),
    }),
  ),
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
  proposal: z
    .object({
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
    })
    .nullable(),
  response_draft: z
    .object({
      id: z.string().min(1),
      version: z.number().int().positive(),
      subject: z.string().min(1),
      body: z.string().min(1),
      status: z.enum(["draft", "ready", "blocked"]),
      updated_at: z.string().datetime(),
    })
    .nullable(),
  proposed_actions: z.array(
    z.object({
      id: z.string().min(1),
      type: z.string().min(1),
      label: z.string().min(1),
      impact: apiMoneySchema.nullable(),
      expected_outcome: z.string().min(1),
      review_required: z.boolean(),
    }),
  ),
  activity: z.array(apiCaseActivitySchema),
  collections: z
    .object({
      business_contexts: apiCollectionWindowSchema,
      messages: apiCollectionWindowSchema,
      activity: apiCollectionWindowSchema,
    })
    .optional(),
  available_commands: z.array(
    z.enum([
      "assign_to_me",
      "request_information",
      "resume_investigation",
      "send_reply",
      "add_note",
      "revise_resolution",
      "save_draft",
      "submit_for_review",
      "escalate",
      "export_audit",
    ]),
  ),
});

const caseListEnvelopeSchema = z.object({
  items: z.array(apiCaseSummarySchema),
  next_cursor: z.string().nullable(),
  previous_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
  offset: z.number().int().nonnegative(),
  limit: z.number().int().positive().max(100),
  summary_scope: z.literal("organization"),
  summary: z.object({
    total: z.number().int().nonnegative(),
    attention: z.number().int().nonnegative(),
    review: z.number().int().nonnegative(),
    sla_at_risk: z.number().int().nonnegative(),
    unassigned: z.number().int().nonnegative(),
  }),
});

const caseDetailEnvelopeSchema = z.object({ data: apiCaseWorkspaceSchema });

function mapSummary(raw: z.infer<typeof apiCaseSummarySchema>): CaseSummary {
  return CaseSummarySchema.parse({
    id: raw.id,
    sourceId: raw.source_id,
    externalReference: raw.external_reference,
    category: raw.category,
    issue: raw.issue,
    customer: {
      name: raw.customer.name,
      isVip: raw.customer.is_vip,
    },
    status: raw.status,
    owner: raw.owner,
    urgency: raw.urgency,
    risk: raw.risk,
    slaMinutesRemaining: raw.sla_minutes_remaining,
    updatedAt: raw.updated_at,
    sourceFreshness: {
      status: raw.source_freshness.status,
      checkedAt: raw.source_freshness.checked_at,
    },
    impact: raw.impact,
    version: raw.version,
  });
}

export function mapApiConversationMessage(
  message: z.infer<typeof apiConversationMessageSchema>,
): CaseConversationMessage {
  return {
    id: message.id,
    authorType: message.author_type,
    authorId: message.author_id,
    authorName: message.author_name,
    channel: message.channel,
    body: message.body,
    internal: message.internal,
    sourceReference: message.source_reference,
    createdAt: message.created_at,
    version: message.version,
  };
}

export function mapApiCaseActivity(
  activity: z.infer<typeof apiCaseActivitySchema>,
): CaseActivity {
  return activity;
}

function mapCollectionWindow(
  raw: z.infer<typeof apiCollectionWindowSchema> | undefined,
  returned: number,
): CaseCollectionWindow {
  return {
    returned: raw?.returned ?? returned,
    total: raw?.total ?? returned,
    hasMore: raw?.has_more ?? false,
    nextCursor: raw?.next_cursor ?? null,
  };
}

function mapWorkspace(
  raw: z.infer<typeof apiCaseWorkspaceSchema>,
): CaseWorkspace {
  return CaseWorkspaceSchema.parse({
    case: mapSummary(raw.case),
    request: {
      receivedAt: raw.request.received_at,
      channel: raw.request.channel,
      customerMessage: raw.request.customer_message,
      summary: raw.request.summary,
    },
    conversation: {
      id: raw.conversation.id,
      version: raw.conversation.version,
      updatedAt: raw.conversation.updated_at,
      messages: raw.conversation.messages.map(mapApiConversationMessage),
    },
    customer: raw.customer,
    businessContexts: raw.business_contexts,
    facts: raw.facts.map((item) => ({
      id: item.id,
      statement: item.statement,
      source: item.source,
      verifiedAt: item.verified_at,
    })),
    missingInformation: raw.missing_information,
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
    responseDraft: raw.response_draft
      ? {
          id: raw.response_draft.id,
          version: raw.response_draft.version,
          subject: raw.response_draft.subject,
          body: raw.response_draft.body,
          status: raw.response_draft.status,
          updatedAt: raw.response_draft.updated_at,
        }
      : null,
    proposedActions: raw.proposed_actions.map((item) => ({
      id: item.id,
      type: item.type,
      label: item.label,
      impact: item.impact,
      expectedOutcome: item.expected_outcome,
      reviewRequired: item.review_required,
    })),
    activity: raw.activity.map(mapApiCaseActivity),
    collections: {
      businessContexts: mapCollectionWindow(
        raw.collections?.business_contexts,
        raw.business_contexts.length,
      ),
      messages: mapCollectionWindow(
        raw.collections?.messages,
        raw.conversation.messages.length,
      ),
      activity: mapCollectionWindow(
        raw.collections?.activity,
        raw.activity.length,
      ),
    },
    availableCommands: raw.available_commands,
  });
}

export const apiCaseRepository: CaseRepository = {
  source: "api",
  async listCases(options: CaseListOptions = {}) {
    const parameters = new URLSearchParams({
      limit: String(options.limit ?? CASE_QUEUE_PAGE_SIZE),
      view: options.view ?? "all",
      sort: options.sort ?? "priority",
    });
    if (options.query) parameters.set("query", options.query);
    if (options.status) parameters.set("status", options.status);
    if (options.category) parameters.set("category", options.category);
    if (options.cursor) parameters.set("cursor", options.cursor);
    const envelope = await apiRequest(
      `/api/cases?${parameters.toString()}`,
      caseListEnvelopeSchema,
    );
    return {
      items: envelope.items.map(mapSummary),
      nextCursor: envelope.next_cursor,
      previousCursor: envelope.previous_cursor,
      total: envelope.total,
      offset: envelope.offset,
      limit: envelope.limit,
      summaryScope: envelope.summary_scope,
      summary: {
        total: envelope.summary.total,
        attention: envelope.summary.attention,
        review: envelope.summary.review,
        slaAtRisk: envelope.summary.sla_at_risk,
        unassigned: envelope.summary.unassigned,
      },
    };
  },
  async getCaseWorkspace(caseId) {
    try {
      const envelope = await apiRequest(
        `/api/cases/${encodeURIComponent(caseId)}`,
        caseDetailEnvelopeSchema,
      );
      return mapWorkspace(envelope.data);
    } catch (error) {
      if (isApiNotFound(error)) return null;
      throw error;
    }
  },
};
