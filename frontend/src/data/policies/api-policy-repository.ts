import { apiRequest, isApiNotFound } from "@/data/api/api-client";
import {
  PolicyDetailSchema,
  PolicySummarySchema,
  type PolicyDetail,
  type PolicySummary,
} from "@/domain/policies/policy";
import { z } from "zod";
import type { PolicyRepository } from "./policy-repository";

const apiPolicySummarySchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  description: z.string().min(1),
  status: z.enum([
    "draft",
    "in_review",
    "published",
    "scheduled",
    "retired",
    "expired",
    "conflicting",
    "parsing_failed",
  ]),
  owner: z.object({ id: z.string().min(1), name: z.string().min(1) }),
  applies_to: z.array(z.string().min(1)),
  current_version: z.number().int().nonnegative(),
  effective_from: z.string().datetime().nullable(),
  effective_to: z.string().datetime().nullable(),
  source: z.object({
    kind: z.enum(["upload", "url", "manual"]),
    name: z.string().min(1),
  }),
  health: z.enum([
    "healthy",
    "review_due",
    "conflict",
    "expired",
    "source_error",
  ]),
  used_by_cases: z.number().int().nonnegative(),
  version: z.number().int().positive(),
  updated_at: z.string().datetime(),
});

const apiPolicyVersionSchema = z.object({
  id: z.string().min(1),
  version: z.number().int().positive(),
  record_version: z.number().int().positive(),
  status: z.enum(["draft", "in_review", "published", "scheduled", "retired"]),
  immutable: z.boolean(),
  created_at: z.string().datetime(),
  published_at: z.string().datetime().nullable(),
  effective_from: z.string().datetime().nullable(),
  effective_to: z.string().datetime().nullable(),
  applicability: z.object({
    decision_scope: z.string().min(1),
    case_categories: z.array(z.string().min(1)).min(1),
    products: z.array(z.string().min(1)).min(1),
    regions: z.array(z.string().min(1)).min(1),
    channels: z.array(z.string().min(1)).min(1),
    customer_tiers: z.array(z.string().min(1)).min(1),
  }),
  source_text: z.string().min(1),
  clauses: z.array(
    z.object({
      id: z.string().min(1),
      heading: z.string().min(1),
      text: z.string().min(1),
      applies_when: z.string().min(1),
    }),
  ),
  used_by_cases: z.array(
    z.object({
      case_id: z.string().min(1),
      citation: z.string().min(1),
      recorded_at: z.string().datetime(),
    }),
  ),
});

const policyListEnvelopeSchema = z.object({
  items: z.array(apiPolicySummarySchema),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
});

const policyDetailEnvelopeSchema = z.object({
  data: z.object({
    policy: apiPolicySummarySchema,
    versions: z.array(apiPolicyVersionSchema),
    available_commands: z.array(
      z.enum([
        "create_draft",
        "submit_review",
        "publish",
        "schedule",
        "retire",
        "retry_source",
      ]),
    ),
  }),
});

function mapSummary(raw: z.infer<typeof apiPolicySummarySchema>): PolicySummary {
  return PolicySummarySchema.parse({
    id: raw.id,
    title: raw.title,
    description: raw.description,
    status: raw.status,
    owner: raw.owner,
    appliesTo: raw.applies_to,
    currentVersion: raw.current_version,
    effectiveFrom: raw.effective_from,
    effectiveTo: raw.effective_to,
    source: raw.source,
    health: raw.health,
    usedByCases: raw.used_by_cases,
    recordVersion: raw.version,
    updatedAt: raw.updated_at,
  });
}

function mapDetail(
  raw: z.infer<typeof policyDetailEnvelopeSchema>["data"],
): PolicyDetail {
  return PolicyDetailSchema.parse({
    policy: mapSummary(raw.policy),
    versions: raw.versions.map((item) => ({
      id: item.id,
      version: item.version,
      recordVersion: item.record_version,
      status: item.status,
      immutable: item.immutable,
      createdAt: item.created_at,
      publishedAt: item.published_at,
      effectiveFrom: item.effective_from,
      effectiveTo: item.effective_to,
      applicability: {
        decisionScope: item.applicability.decision_scope,
        caseCategories: item.applicability.case_categories,
        products: item.applicability.products,
        regions: item.applicability.regions,
        channels: item.applicability.channels,
        customerTiers: item.applicability.customer_tiers,
      },
      sourceText: item.source_text,
      clauses: item.clauses.map((clause) => ({
        id: clause.id,
        heading: clause.heading,
        text: clause.text,
        appliesWhen: clause.applies_when,
      })),
      usedByCases: item.used_by_cases.map((reference) => ({
        caseId: reference.case_id,
        citation: reference.citation,
        recordedAt: reference.recorded_at,
      })),
    })),
    availableCommands: raw.available_commands,
  });
}

export const apiPolicyRepository: PolicyRepository = {
  source: "api",
  async listPolicies() {
    const envelope = await apiRequest(
      "/api/policies?limit=100",
      policyListEnvelopeSchema,
    );
    return envelope.items.map(mapSummary);
  },
  async getPolicyDetail(policyId) {
    try {
      const envelope = await apiRequest(
        `/api/policies/${encodeURIComponent(policyId)}`,
        policyDetailEnvelopeSchema,
      );
      return mapDetail(envelope.data);
    } catch (error) {
      if (isApiNotFound(error)) return null;
      throw error;
    }
  },
};
