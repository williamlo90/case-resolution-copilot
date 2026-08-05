import { PolicyDetailSchema, PolicySummarySchema, type PolicyDetail, type PolicySummary } from "@/domain/policies/policy";

const base = { owner: { id: "USR-AD", name: "Avery Daniels" }, source: { kind: "upload", name: "Operations policy handbook.pdf" }, recordVersion: 1, updatedAt: "2026-07-21T04:20:00.000Z" } as const;
const rawPolicies = [
  { ...base, id: "POL-1008", title: "Billing adjustments", description: "Rules for duplicate charges, credits, and payment corrections.", status: "published", appliesTo: ["Billing disputes", "Refund requests"], currentVersion: 3, effectiveFrom: "2026-06-01T00:00:00.000Z", effectiveTo: null, health: "healthy", usedByCases: 42 },
  { ...base, id: "POL-1007", title: "Account recovery", description: "Identity verification and safe account restoration requirements.", status: "in_review", appliesTo: ["Account access"], currentVersion: 2, effectiveFrom: null, effectiveTo: null, health: "review_due", usedByCases: 18 },
  { ...base, id: "POL-1006", title: "Service exceptions", description: "Resolution limits for damaged orders and delivery failures.", status: "scheduled", appliesTo: ["Service exceptions"], currentVersion: 4, effectiveFrom: "2026-08-01T00:00:00.000Z", effectiveTo: null, health: "healthy", usedByCases: 31 },
  { ...base, id: "POL-1005", title: "Legacy refund thresholds", description: "Previous refund authority limits retained for audit history.", status: "retired", appliesTo: ["Refund requests"], currentVersion: 5, effectiveFrom: "2025-01-01T00:00:00.000Z", effectiveTo: "2026-05-31T23:59:59.000Z", health: "healthy", usedByCases: 126 },
  { ...base, id: "POL-1004", title: "Temporary goodwill credits", description: "Time-limited authority for customer goodwill credits.", status: "expired", appliesTo: ["Billing disputes"], currentVersion: 1, effectiveFrom: "2026-01-01T00:00:00.000Z", effectiveTo: "2026-06-30T23:59:59.000Z", health: "expired", usedByCases: 9 },
  { ...base, id: "POL-1003", title: "Priority account exceptions", description: "Special handling rules with an unresolved authority overlap.", status: "conflicting", appliesTo: ["Account access", "Service exceptions"], currentVersion: 2, effectiveFrom: "2026-04-01T00:00:00.000Z", effectiveTo: null, health: "conflict", usedByCases: 7 },
  { ...base, id: "POL-1002", title: "International payment guide", description: "Imported payment handling guidance that needs source repair.", status: "parsing_failed", appliesTo: ["Billing disputes"], currentVersion: 1, effectiveFrom: null, effectiveTo: null, health: "source_error", usedByCases: 0 },
  { ...base, id: "POL-1001", title: "Subscription cancellation", description: "Draft rules for unexpected subscription cancellations.", status: "draft", appliesTo: ["Service exceptions"], currentVersion: 1, effectiveFrom: null, effectiveTo: null, health: "review_due", usedByCases: 0 },
] as const;

export const policySummaryFixtures: readonly PolicySummary[] = PolicySummarySchema.array().parse(rawPolicies);

export const policyDetailFixtures: readonly PolicyDetail[] = policySummaryFixtures.map((policy) => PolicyDetailSchema.parse({
  policy,
  versions: [
    { id: `${policy.id}-V${policy.currentVersion}`, version: policy.currentVersion, recordVersion: 1, status: ["expired", "conflicting", "parsing_failed"].includes(policy.status) ? "published" : policy.status === "draft" ? "draft" : policy.status, immutable: policy.status !== "draft" && policy.status !== "in_review", createdAt: "2026-05-20T08:00:00.000Z", publishedAt: policy.status === "draft" || policy.status === "in_review" || policy.status === "parsing_failed" ? null : "2026-05-28T09:00:00.000Z", effectiveFrom: policy.effectiveFrom, effectiveTo: policy.effectiveTo,
      applicability: { decisionScope: "support_resolution", caseCategories: ["all"], products: ["all"], regions: ["all"], channels: ["all"], customerTiers: ["all"] },
      sourceText: `${policy.title}. This source defines approved operational handling and authority boundaries.`, clauses: [
        { id: `${policy.id}-C1`, heading: "Eligibility", text: "The case must match the documented category and contain verified source evidence.", appliesWhen: policy.appliesTo.join(" or ") },
        { id: `${policy.id}-C2`, heading: "Authority", text: "Consequential actions require the authority level recorded with the reviewed proposal.", appliesWhen: "The proposed action changes a customer account or financial record." },
      ], usedByCases: policy.usedByCases ? [{ caseId: "CS-2048", citation: "Eligibility, clause 1", recordedAt: "2026-07-21T03:24:00.000Z" }] : [] },
    ...(policy.currentVersion > 1 ? [{ id: `${policy.id}-V${policy.currentVersion - 1}`, version: policy.currentVersion - 1, recordVersion: 1, status: "retired", immutable: true, createdAt: "2026-01-10T08:00:00.000Z", publishedAt: "2026-01-15T09:00:00.000Z", effectiveFrom: "2026-01-15T00:00:00.000Z", effectiveTo: "2026-05-31T23:59:59.000Z", applicability: { decisionScope: "support_resolution", caseCategories: ["all"], products: ["all"], regions: ["all"], channels: ["all"], customerTiers: ["all"] }, sourceText: `Previous published version of ${policy.title}.`, clauses: [{ id: `${policy.id}-OLD-C1`, heading: "Previous eligibility", text: "Historical handling rule retained for audit evidence.", appliesWhen: "Cases decided under the previous version." }], usedByCases: [{ caseId: "CS-2042", citation: "Previous eligibility", recordedAt: "2026-04-12T03:24:00.000Z" }] }] : []),
  ],
  availableCommands: policy.status === "published" ? ["create_draft", "retire"] : policy.status === "draft" ? ["submit_review"] : policy.status === "in_review" ? ["publish", "schedule"] : policy.status === "parsing_failed" ? ["retry_source"] : [],
}));

export const publishedPolicyFixture = policyDetailFixtures[0];
