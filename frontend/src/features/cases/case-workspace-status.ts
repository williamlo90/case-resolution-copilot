import type { CaseWorkspace } from "@/domain/cases/case";
import type { InboxDraftDelivery } from "@/domain/connections/connected-inbox";
import { caseStatusPresentation } from "@/features/cases/case-presentation";

type WorkspaceStatusPresentation = {
  label: string;
  tone: "neutral" | "warning" | "info" | "danger" | "success";
};

const approvedDeliveryPresentation: Record<
  InboxDraftDelivery["status"],
  WorkspaceStatusPresentation
> = {
  ready: { label: "Approved, creating Gmail draft", tone: "info" },
  running: { label: "Approved, creating Gmail draft", tone: "info" },
  completed: { label: "Approved, Gmail draft ready", tone: "success" },
  failed_safe: { label: "Approved, draft not created", tone: "warning" },
  outcome_unknown: { label: "Approved, check Gmail", tone: "warning" },
  recovery_required: { label: "Approved, reconnect Gmail", tone: "warning" },
};

export function resolveCaseWorkspaceStatus(
  workspace: Pick<CaseWorkspace, "case" | "proposal" | "responseDraft">,
  draftDelivery: InboxDraftDelivery | null | undefined,
): WorkspaceStatusPresentation {
  const caseStatus = caseStatusPresentation[workspace.case.status];
  if (workspace.proposal?.state !== "approved") return caseStatus;

  if (draftDelivery) return approvedDeliveryPresentation[draftDelivery.status];

  return workspace.responseDraft?.status === "ready"
    ? { label: "Approved, draft ready", tone: "success" }
    : { label: "Approved", tone: "success" };
}
