import type { CaseWorkspace } from "@/domain/cases/case";

export type CaseWorkflowMode =
  | "start_investigation"
  | "request_information"
  | "resume_investigation";

type CaseCommand = CaseWorkspace["availableCommands"][number];

const workflowOrder: readonly CaseWorkflowMode[] = [
  "start_investigation",
  "request_information",
  "resume_investigation",
];

export function caseWorkflowModes(
  commands: readonly CaseCommand[],
): CaseWorkflowMode[] {
  return workflowOrder.filter((command) => commands.includes(command));
}

export function caseWorkflowTarget(
  mode: CaseWorkflowMode,
): "information_needed" | "investigating" {
  return mode === "request_information" ? "information_needed" : "investigating";
}
