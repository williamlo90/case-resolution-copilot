import { describe, expect, it } from "vitest";
import { buildOnboardingSteps } from "./onboarding-readiness";

describe("buildOnboardingSteps", () => {
  it("points to the first incomplete real prerequisite", () => {
    const steps = buildOnboardingSteps({
      workspaceConfigured: true,
      hasOperatingTeam: false,
      hasPublishedPolicy: false,
      hasCaseSource: true,
      hasActionTarget: true,
      hasApprovalRule: true,
      hasConfigurationTest: false,
    });

    expect(steps.map((step) => [step.id, step.status])).toEqual([
      ["workspace", "complete"],
      ["team", "current"],
      ["policy", "pending"],
      ["case_source", "complete"],
      ["action_target", "complete"],
      ["approval_rule", "complete"],
      ["test_case", "pending"],
      ["activation", "pending"],
    ]);
  });

  it("marks every prerequisite complete only when all records are ready", () => {
    const steps = buildOnboardingSteps({
      workspaceConfigured: true,
      hasOperatingTeam: true,
      hasPublishedPolicy: true,
      hasCaseSource: true,
      hasActionTarget: true,
      hasApprovalRule: true,
      hasConfigurationTest: true,
    });

    expect(steps.every((step) => step.status === "complete")).toBe(true);
    expect(steps).toHaveLength(8);
  });
});
