import { z } from "zod";

export const QualityCategorySchema = z.enum([
  "decision_quality",
  "safety",
  "reliability",
]);

export const QualityMetricSchema = z.object({
  key: z.string().min(1),
  label: z.string().min(1),
  value: z.number(),
  unit: z.string().min(1),
  numerator: z.number().int().nonnegative().nullable(),
  denominator: z.number().int().nonnegative().nullable(),
  status: z.string().min(1),
  filteredCaseIds: z.array(z.string().min(1)),
});

export const QualityEvidenceSchema = z.object({
  id: z.string().min(1),
  caseId: z.string().min(1),
  category: QualityCategorySchema,
  scenario: z.string().min(1),
  expectedDecision: z.string().min(1),
  observedDecision: z.string().min(1),
  policyEvidence: z.string().min(1),
  policyEvidencePresent: z.boolean(),
  customerOrBusinessImpact: z.string().nullable(),
  result: z.enum(["passed", "needs_attention"]),
  evaluatedBy: z.object({
    id: z.string().min(1),
    name: z.string().min(1),
  }),
  source: z.enum(["deterministic_demo", "manual", "imported"]),
  version: z.number().int().positive(),
  evaluatedAt: z.string().datetime(),
});

export const QualityDashboardSchema = z.object({
  organizationId: z.string().min(1),
  metrics: z.array(QualityMetricSchema),
  operational: z.object({
    openCases: z.number().int().nonnegative(),
    casesWaitingForReview: z.number().int().nonnegative(),
    actionsCompleted: z.number().int().nonnegative(),
    actionsFailedSafe: z.number().int().nonnegative(),
    actionsOutcomeUnknown: z.number().int().nonnegative(),
    reopenedCases: z.number().int().nonnegative().nullable(),
  }),
  evidence: z.array(QualityEvidenceSchema),
  availableCategories: z.array(QualityCategorySchema),
  generatedAt: z.string().datetime(),
  sourceUpdatedAt: z.string().datetime().nullable(),
  total: z.number().int().nonnegative(),
});

export type QualityCategory = z.infer<typeof QualityCategorySchema>;
export type QualityDashboard = z.infer<typeof QualityDashboardSchema>;
