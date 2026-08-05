import {
  OnboardingStepSchema,
  type OnboardingStep,
} from "@/domain/administration/administration";

export type OnboardingReadinessInput = {
  workspaceConfigured: boolean;
  hasOperatingTeam: boolean;
  hasPublishedPolicy: boolean;
  hasCaseSource: boolean;
  hasActionTarget: boolean;
  hasApprovalRule: boolean;
  hasConfigurationTest: boolean;
};

export function buildOnboardingSteps(
  readiness: OnboardingReadinessInput,
): readonly OnboardingStep[] {
  const checks = [
    {
      id: "workspace",
      label: "Workspace details",
      description: "Confirm the organization name, time zone, and locale.",
      complete: readiness.workspaceConfigured,
    },
    {
      id: "team",
      label: "Operating team",
      description: "Keep an active reviewer available for decisions that need approval.",
      complete: readiness.hasOperatingTeam,
    },
    {
      id: "policy",
      label: "Published policy",
      description: "Publish at least one policy that can support a decision.",
      complete: readiness.hasPublishedPolicy,
    },
    {
      id: "case_source",
      label: "Case source",
      description: "Confirm that live or clearly labeled demo cases reach the workspace.",
      complete: readiness.hasCaseSource,
    },
    {
      id: "action_target",
      label: "Action target",
      description: "Verify a live, test, or demo tool for controlled changes.",
      complete: readiness.hasActionTarget,
    },
    {
      id: "approval_rule",
      label: "Approval rule",
      description: "Confirm financial limits and required decision reasons.",
      complete: readiness.hasApprovalRule,
    },
    {
      id: "test_case",
      label: "Configuration test",
      description: "Generate at least one Decision Brief from current case and policy data.",
      complete: readiness.hasConfigurationTest,
    },
    {
      id: "activation",
      label: "Workspace ready",
      description: "All required checks must pass before controlled pilot work begins.",
      complete: Object.values(readiness).every(Boolean),
    },
  ];

  let currentAssigned = false;
  return OnboardingStepSchema.array().parse(
    checks.map((check) => {
      let status: OnboardingStep["status"];
      if (check.complete) {
        status = "complete";
      } else if (!currentAssigned) {
        status = "current";
        currentAssigned = true;
      } else {
        status = "pending";
      }
      return {
        id: check.id,
        label: check.label,
        description: check.description,
        status,
      };
    }),
  );
}
