import { evaluatedDatasetFixture } from "@/mocks/fixtures/evaluation-fixtures";
import {
  QualityDashboardSchema,
  type QualityDashboard,
} from "@/domain/quality/quality";
import type { QualityRepository } from "./quality-repository";

const generatedAt = evaluatedDatasetFixture.evaluatedAt;

const dashboard: QualityDashboard = QualityDashboardSchema.parse({
  organizationId: "ORG-0001",
  metrics: [
    {
      key: "expected_decisions",
      label: "Expected decisions",
      value: evaluatedDatasetFixture.summary.passRate,
      unit: "percent",
      numerator: evaluatedDatasetFixture.summary.passed,
      denominator: evaluatedDatasetFixture.summary.total,
      status:
        evaluatedDatasetFixture.summary.failed === 0
          ? "healthy"
          : "needs_attention",
      filteredCaseIds: [],
    },
    {
      key: "unsafe_actions_blocked",
      label: "Unsafe actions blocked",
      value: 100,
      unit: "percent",
      numerator: 1,
      denominator: 1,
      status: "healthy",
      filteredCaseIds: [],
    },
    {
      key: "policy_evidence_present",
      label: "Policy evidence present",
      value: 92,
      unit: "percent",
      numerator: 11,
      denominator: 12,
      status: "needs_attention",
      filteredCaseIds: [],
    },
    {
      key: "outcome_checks_pending",
      label: "Outcome checks pending",
      value: 1,
      unit: "count",
      numerator: null,
      denominator: null,
      status: "needs_attention",
      filteredCaseIds: [],
    },
  ],
  operational: {
    openCases: 9,
    casesWaitingForReview: 2,
    actionsCompleted: 4,
    actionsFailedSafe: 1,
    actionsOutcomeUnknown: 1,
    reopenedCases: null,
  },
  evidence: evaluatedDatasetFixture.cases.map((item, index) => ({
    id: `QLT-MOCK-${String(index + 1).padStart(3, "0")}`,
    caseId: item.id,
    category:
      item.category === "failure_recovery"
        ? "reliability"
        : item.category === "safety"
          ? "safety"
          : "decision_quality",
    scenario: item.scenario,
    expectedDecision: item.expectedDecision,
    observedDecision: item.actualDecision,
    policyEvidence: item.policyCitation,
    policyEvidencePresent: Boolean(item.policyCitation),
    customerOrBusinessImpact: item.impact,
    result: item.result === "passed" ? "passed" : "needs_attention",
    evaluatedBy: { id: "USR-0004", name: "Nadia Auditor" },
    source: "deterministic_demo",
    version: 1,
    evaluatedAt: generatedAt,
  })),
  availableCategories: ["decision_quality", "safety", "reliability"],
  generatedAt,
  sourceUpdatedAt: generatedAt,
  total: evaluatedDatasetFixture.summary.total,
});

export const mockQualityRepository: QualityRepository = {
  source: "mock",
  async getDashboard() {
    return structuredClone(dashboard);
  },
};
