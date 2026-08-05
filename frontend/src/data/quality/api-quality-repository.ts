import { apiRequest } from "@/data/api/api-client";
import {
  QualityDashboardSchema,
  type QualityDashboard,
} from "@/domain/quality/quality";
import { z } from "zod";
import type { QualityRepository } from "./quality-repository";

const qualityEnvelopeSchema = z.object({
  data: z.object({
    organization_id: z.string().min(1),
    metrics: z.array(
      z.object({
        key: z.string().min(1),
        label: z.string().min(1),
        value: z.number(),
        unit: z.string().min(1),
        numerator: z.number().int().nonnegative().nullable(),
        denominator: z.number().int().nonnegative().nullable(),
        status: z.string().min(1),
        filtered_case_ids: z.array(z.string().min(1)),
      }),
    ),
    operational: z.object({
      open_cases: z.number().int().nonnegative(),
      cases_waiting_for_review: z.number().int().nonnegative(),
      actions_completed: z.number().int().nonnegative(),
      actions_failed_safe: z.number().int().nonnegative(),
      actions_outcome_unknown: z.number().int().nonnegative(),
      reopened_cases: z.number().int().nonnegative().nullable(),
    }),
    evidence: z.array(
      z.object({
        id: z.string().min(1),
        case_id: z.string().min(1),
        category: z.enum(["decision_quality", "safety", "reliability"]),
        scenario: z.string().min(1),
        expected_decision: z.string().min(1),
        observed_decision: z.string().min(1),
        policy_evidence: z.string().min(1),
        policy_evidence_present: z.boolean(),
        customer_or_business_impact: z.string().nullable(),
        result: z.enum(["passed", "needs_attention"]),
        evaluated_by: z.object({
          id: z.string().min(1),
          name: z.string().min(1),
        }),
        source: z.enum(["deterministic_demo", "manual", "imported"]),
        version: z.number().int().positive(),
        evaluated_at: z.string().datetime(),
      }),
    ),
    available_categories: z.array(
      z.enum(["decision_quality", "safety", "reliability"]),
    ),
    generated_at: z.string().datetime(),
    source_updated_at: z.string().datetime().nullable(),
    total: z.number().int().nonnegative(),
  }),
});

function mapDashboard(
  raw: z.infer<typeof qualityEnvelopeSchema>["data"],
): QualityDashboard {
  return QualityDashboardSchema.parse({
    organizationId: raw.organization_id,
    metrics: raw.metrics.map((item) => ({
      key: item.key,
      label: item.label,
      value: item.value,
      unit: item.unit,
      numerator: item.numerator,
      denominator: item.denominator,
      status: item.status,
      filteredCaseIds: item.filtered_case_ids,
    })),
    operational: {
      openCases: raw.operational.open_cases,
      casesWaitingForReview: raw.operational.cases_waiting_for_review,
      actionsCompleted: raw.operational.actions_completed,
      actionsFailedSafe: raw.operational.actions_failed_safe,
      actionsOutcomeUnknown: raw.operational.actions_outcome_unknown,
      reopenedCases: raw.operational.reopened_cases,
    },
    evidence: raw.evidence.map((item) => ({
      id: item.id,
      caseId: item.case_id,
      category: item.category,
      scenario: item.scenario,
      expectedDecision: item.expected_decision,
      observedDecision: item.observed_decision,
      policyEvidence: item.policy_evidence,
      policyEvidencePresent: item.policy_evidence_present,
      customerOrBusinessImpact: item.customer_or_business_impact,
      result: item.result,
      evaluatedBy: item.evaluated_by,
      source: item.source,
      version: item.version,
      evaluatedAt: item.evaluated_at,
    })),
    availableCategories: raw.available_categories,
    generatedAt: raw.generated_at,
    sourceUpdatedAt: raw.source_updated_at,
    total: raw.total,
  });
}

export const apiQualityRepository: QualityRepository = {
  source: "api",
  async getDashboard() {
    const envelope = await apiRequest("/api/quality", qualityEnvelopeSchema);
    return mapDashboard(envelope.data);
  },
};
