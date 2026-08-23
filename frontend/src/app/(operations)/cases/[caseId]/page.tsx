import { getCaseRepository } from "@/data/cases/case-repository-provider";
import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { ApiClientError } from "@/data/api/api-client";
import { apiInboxDraftRepository } from "@/data/connections/api-inbox-draft-repository";
import type { InboxDraftDelivery } from "@/domain/connections/connected-inbox";
import { CaseWorkspace } from "@/features/cases/components/case-workspace";
import { notFound } from "next/navigation";
import {
  addCaseEvidence,
  addCaseConversationEntry,
  loadCaseActivityHistory,
  loadCaseConversationHistory,
  prepareCaseDecisionBrief,
  saveCaseDraft,
  submitCaseReview,
  updateCaseWorkflow,
} from "../../_actions/cases";
import {
  deliverResponseDraft,
  reconcileResponseDraft,
} from "../../_actions/inbox-drafts";

export default async function CaseWorkspacePage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = await params;
  const repository = getCaseRepository();
  const connected = repository.source === "api";
  const [workspace, sessionContext] = await Promise.all([
    repository.getCaseWorkspace(caseId),
    connected
      ? getAdministrationRepository().getSessionContext()
      : Promise.resolve(null),
  ]);
  if (!workspace) notFound();
  const canManageCase =
    sessionContext?.actor.permissions.includes("case:manage") ?? false;
  const inboxCase = workspace.case.sourceId.startsWith("inbox:");
  let latestDraftDelivery: InboxDraftDelivery | null = null;
  if (connected && canManageCase && inboxCase && workspace.responseDraft) {
    try {
      latestDraftDelivery = await apiInboxDraftRepository.getLatest(
        workspace.case.id,
        workspace.responseDraft.version,
      );
    } catch (error) {
      if (!(error instanceof ApiClientError)) throw error;
    }
  }
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
      addEvidenceAction={
        connected && workspace.availableCommands.includes("add_evidence")
          ? addCaseEvidence.bind(
              null,
              workspace.case.id,
              workspace.case.version,
            )
          : undefined
      }
      deliverDraftAction={
        connected && canManageCase && inboxCase && workspace.responseDraft
          ? deliverResponseDraft.bind(
              null,
              workspace.case.id,
              workspace.responseDraft.version,
            )
          : undefined
      }
      reconcileDraftAction={
        connected && canManageCase && inboxCase && workspace.responseDraft
          ? reconcileResponseDraft
          : undefined
      }
      initialDraftDelivery={canManageCase ? latestDraftDelivery : null}
    />
  );
}
