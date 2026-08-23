import { z } from "zod";

export const MoneySchema = z.object({
  amount: z.number().nonnegative(),
  currency: z.string().regex(/^[A-Z]{3}$/),
});

export const PublicCaseIdSchema = z.string().regex(/^CS-[A-Z0-9-]+$/);

export const CaseStatusSchema = z.enum([
  "new",
  "investigating",
  "information_needed",
  "needs_review",
  "waiting_customer",
  "in_progress",
  "completed",
]);

export const CaseCategorySchema = z.enum([
  "billing_dispute",
  "refund_request",
  "account_access",
  "service_exception",
]);

export const CaseOwnerSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  initials: z.string().min(1).max(3),
}).nullable();

export const CaseSummarySchema = z.object({
  id: PublicCaseIdSchema,
  sourceId: z.string().min(1),
  externalReference: z.string().min(1),
  category: CaseCategorySchema,
  issue: z.string().min(1),
  customer: z.object({
    name: z.string().min(1),
    isVip: z.boolean(),
  }),
  status: CaseStatusSchema,
  owner: CaseOwnerSchema,
  urgency: z.enum(["low", "medium", "high", "critical"]),
  risk: z.enum(["low", "medium", "high"]),
  slaMinutesRemaining: z.number().int().nonnegative(),
  updatedAt: z.string().datetime().nullable(),
  sourceFreshness: z.object({
    status: z.enum(["current", "stale", "unavailable"]),
    checkedAt: z.string().datetime().nullable(),
  }),
  impact: MoneySchema.nullable(),
  version: z.number().int().positive().default(1),
});

export const CaseProposalSchema = z.object({
  id: z.string().min(1),
  version: z.number().int().positive(),
  outcome: z.string().min(1),
  impact: MoneySchema.nullable(),
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

export const CaseResponseDraftSchema = z.object({
  id: z.string().min(1),
  version: z.number().int().positive(),
  subject: z.string().min(1),
  body: z.string().min(1),
  status: z.enum(["draft", "ready", "blocked"]),
  updatedAt: z.string().datetime(),
});

export const CaseConversationMessageSchema = z.object({
  id: z.string().min(1),
  authorType: z.enum(["customer", "member", "service", "system"]),
  authorId: z.string().min(1).nullable(),
  authorName: z.string().min(1),
  channel: z.enum(["email", "chat", "phone", "webhook", "internal_note"]),
  body: z.string().min(1),
  internal: z.boolean(),
  sourceReference: z.string().min(1).nullable(),
  createdAt: z.string().datetime(),
  version: z.number().int().positive(),
});

export const CaseActivitySchema = z.object({
  id: z.string().min(1),
  label: z.string().min(1),
  detail: z.string().min(1),
  actor: z.string().min(1),
  timestamp: z.string().datetime(),
  status: z.enum(["completed", "current", "waiting", "failed"]),
});

export const CaseCollectionWindowSchema = z.object({
  returned: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
  hasMore: z.boolean(),
  nextCursor: z.string().min(1).nullable(),
});

export const CaseWorkspaceSchema = z.object({
  case: CaseSummarySchema,
  request: z.object({
    receivedAt: z.string().datetime(),
    channel: z.enum(["email", "chat", "phone", "webhook"]),
    customerMessage: z.string().min(1),
    summary: z.string().min(1),
  }),
  conversation: z.object({
    id: z.string().min(1),
    version: z.number().int().positive(),
    updatedAt: z.string().datetime(),
    messages: z.array(CaseConversationMessageSchema),
  }),
  customer: z.object({
    id: z.string().min(1),
    tier: z.enum(["standard", "vip", "enterprise"]),
    locale: z.string().min(1),
    contact: z.string().min(1),
  }),
  businessContexts: z.array(z.object({
    id: z.string().min(1),
    type: z.enum(["invoice", "payment", "subscription", "account", "order", "delivery", "other"]),
    label: z.string().min(1),
    source: z.string().min(1),
    status: z.string().min(1),
    fields: z.record(z.string(), z.string()),
  })),
  facts: z.array(z.object({
    id: z.string().min(1),
    statement: z.string().min(1),
    source: z.string().min(1),
    verifiedAt: z.string().datetime(),
  })),
  missingInformation: z.array(z.object({
    id: z.string().min(1),
    label: z.string().min(1),
    description: z.string().min(1),
    blocking: z.boolean(),
  })),
  evidence: z.array(z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    citation: z.string().min(1),
    excerpt: z.string().min(1),
    applicability: z.string().min(1),
    effectiveDate: z.string().min(1),
    freshness: z.enum(["current", "stale"]),
    conflictState: z.enum(["none", "possible", "confirmed"]),
  })),
  risks: z.array(z.object({
    id: z.string().min(1),
    label: z.string().min(1),
    outcome: z.enum(["passed", "requires_review", "information_needed", "blocked"]),
    explanation: z.string().min(1),
  })),
  proposal: CaseProposalSchema.nullable(),
  responseDraft: CaseResponseDraftSchema.nullable(),
  proposedActions: z.array(z.object({
    id: z.string().min(1),
    type: z.string().min(1),
    label: z.string().min(1),
    impact: MoneySchema.nullable(),
    expectedOutcome: z.string().min(1),
    reviewRequired: z.boolean(),
  })),
  activity: z.array(CaseActivitySchema),
  collections: z.object({
    businessContexts: CaseCollectionWindowSchema,
    messages: CaseCollectionWindowSchema,
    activity: CaseCollectionWindowSchema,
  }),
  availableCommands: z.array(z.enum([
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
  ])),
});

export type CaseStatus = z.infer<typeof CaseStatusSchema>;
export type CaseCategory = z.infer<typeof CaseCategorySchema>;
export type CaseOwner = z.infer<typeof CaseOwnerSchema>;
export type CaseSummary = z.infer<typeof CaseSummarySchema>;
export type CaseConversationMessage = z.infer<
  typeof CaseConversationMessageSchema
>;
export type CaseActivity = z.infer<typeof CaseActivitySchema>;
export type CaseCollectionWindow = z.infer<
  typeof CaseCollectionWindowSchema
>;
export type CaseWorkspace = z.infer<typeof CaseWorkspaceSchema>;
