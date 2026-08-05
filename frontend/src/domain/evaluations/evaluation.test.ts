import { describe, expect, it } from "vitest";
import {
  evaluatedDatasetFixture,
  goldenDatasetFixture,
  observedWorkflowOutputFixture,
} from "@/mocks/fixtures/evaluation-fixtures";
import { evaluateDataset } from "./evaluation";

describe("deterministic evaluation", () => {
  it("joins separate golden expectations and observed workflow output", () => {
    const result = evaluateDataset(
      goldenDatasetFixture,
      observedWorkflowOutputFixture,
    );

    expect(result.goldenVersion).toBe("support-escalation-v2.0");
    expect(result.observedVersion).toBe("workflow-output-v2");
    expect(result.summary).toEqual({
      total: 8,
      passed: 7,
      failed: 1,
      passRate: 88,
    });
  });

  it("keeps the delayed-postcondition gap visible", () => {
    const knownFailure = evaluatedDatasetFixture.cases.find(
      (item) => item.id === "EVAL-008",
    );

    expect(knownFailure?.result).toBe("failed");
    expect(knownFailure?.failedChecks).toEqual([
      "postcondition",
    ]);
    expect(knownFailure?.safetyDisposition).toContain("No retry");
  });

  it("fails when an observed result is missing", () => {
    const incompleteOutput = {
      ...observedWorkflowOutputFixture,
      results: observedWorkflowOutputFixture.results.slice(0, -1),
    };

    expect(() =>
      evaluateDataset(goldenDatasetFixture, incompleteOutput),
    ).toThrow("Missing observed result for EVAL-008");
  });
});
