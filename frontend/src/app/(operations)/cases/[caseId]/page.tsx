import { getCaseRepository } from "@/data/cases/case-repository-provider";
import { CaseWorkspace } from "@/features/cases/components/case-workspace";
import { notFound } from "next/navigation";
import {
  addCaseConversationEntry,
  loadCaseActivityHistory,
  loadCaseConversationHistory,
  prepareCaseDecisionBrief,
  saveCaseDraft,
  submitCaseReview,
  updateCaseWorkflow,
} from "../../_actions/cases";

export default async function CaseWorkspacePage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  const repository = getCaseRepository();
  const workspace = await repository.getCaseWorkspace(caseId);
  if (!workspace) notFound();
  const connected = repository.source === "api";
  const replyChannel =
    workspace.request.channel === "webhook"
      ? "email"
      : workspace.request.channel;
  return (
    <CaseWorkspace
      workspace={workspace}
      workflowAction={
        connected && workspace.availableCommands.includes("request_information")
          ? {
              mode: "request_information",
              action: updateCaseWorkflow.bind(
                null,
                workspace.case.id,
                workspace.case.version,
                "information_needed",
              ),
            }
          : connected && workspace.availableCommands.includes("resume_investigation")
            ? {
                mode: "resume_investigation",
                action: updateCaseWorkflow.bind(
                  null,
                  workspace.case.id,
                  workspace.case.version,
                  "investigating",
                ),
              }
            : undefined
      }
      prepareBriefAction={
        connected && workspace.availableCommands.includes("revise_resolution")
          ? prepareCaseDecisionBrief.bind(
              null,
              workspace.case.id,
              workspace.case.version,
              workspace.proposal?.version ?? 0,
            )
          : undefined
      }
      submitReviewAction={
        connected && workspace.proposal
          ? submitCaseReview.bind(
              null,
              workspace.case.id,
              workspace.proposal.version,
              workspace.case.version,
            )
          : undefined
      }
      saveDraftAction={
        connected && workspace.availableCommands.includes("save_draft")
          ? saveCaseDraft.bind(
              null,
              workspace.case.id,
              workspace.responseDraft?.version ?? 0,
            )
          : undefined
      }
      addReplyAction={
        connected && workspace.availableCommands.includes("send_reply")
          ? addCaseConversationEntry.bind(
              null,
              workspace.case.id,
              workspace.case.version,
              "reply",
              replyChannel,
            )
          : undefined
      }
      addNoteAction={
        connected && workspace.availableCommands.includes("add_note")
          ? addCaseConversationEntry.bind(
              null,
              workspace.case.id,
              workspace.case.version,
              "note",
              replyChannel,
            )
          : undefined
      }
      loadConversationHistoryAction={
        connected && workspace.collections.messages.nextCursor
          ? loadCaseConversationHistory.bind(null, workspace.case.id)
          : undefined
      }
      loadActivityHistoryAction={
        connected && workspace.collections.activity.nextCursor
          ? loadCaseActivityHistory.bind(null, workspace.case.id)
          : undefined
      }
    />
  );
}
