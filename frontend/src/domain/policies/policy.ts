import { z } from "zod";

export const PolicyStatusSchema = z.enum(["draft", "in_review", "published", "scheduled", "retired", "expired", "conflicting", "parsing_failed"]);

export const PolicySummarySchema = z.object({
  id: z.string().regex(/^POL-[A-Z0-9-]+$/), title: z.string().min(1), description: z.string().min(1), status: PolicyStatusSchema,
  owner: z.object({ id: z.string().min(1), name: z.string().min(1) }), appliesTo: z.array(z.string().min(1)).min(1),
  currentVersion: z.number().int().positive(), effectiveFrom: z.string().datetime().nullable(), effectiveTo: z.string().datetime().nullable(),
  source: z.object({ kind: z.enum(["upload", "url", "manual"]), name: z.string().min(1) }),
  health: z.enum(["healthy", "review_due", "conflict", "expired", "source_error"]), usedByCases: z.number().int().nonnegative(), recordVersion: z.number().int().positive(), updatedAt: z.string().datetime(),
});

export const PolicyVersionSchema = z.object({
  id: z.string().min(1), version: z.number().int().positive(), recordVersion: z.number().int().positive(), status: z.enum(["draft", "in_review", "published", "scheduled", "retired"]), immutable: z.boolean(),
  createdAt: z.string().datetime(), publishedAt: z.string().datetime().nullable(), effectiveFrom: z.string().datetime().nullable(), effectiveTo: z.string().datetime().nullable(),
  applicability: z.object({
    decisionScope: z.string().min(1),
    caseCategories: z.array(z.string().min(1)).min(1),
    products: z.array(z.string().min(1)).min(1),
    regions: z.array(z.string().min(1)).min(1),
    channels: z.array(z.string().min(1)).min(1),
    customerTiers: z.array(z.string().min(1)).min(1),
  }),
  sourceText: z.string().min(1), clauses: z.array(z.object({ id: z.string().min(1), heading: z.string().min(1), text: z.string().min(1), appliesWhen: z.string().min(1) })).min(1),
  usedByCases: z.array(z.object({ caseId: z.string().regex(/^CS-[A-Z0-9-]+$/), citation: z.string().min(1), recordedAt: z.string().datetime() })),
});

export const PolicyDetailSchema = z.object({ policy: PolicySummarySchema, versions: z.array(PolicyVersionSchema).min(1), availableCommands: z.array(z.enum(["create_draft", "submit_review", "publish", "schedule", "retire", "retry_source"])) });

export type PolicyStatus = z.infer<typeof PolicyStatusSchema>;
export type PolicySummary = z.infer<typeof PolicySummarySchema>;
export type PolicyVersion = z.infer<typeof PolicyVersionSchema>;
export type PolicyDetail = z.infer<typeof PolicyDetailSchema>;
