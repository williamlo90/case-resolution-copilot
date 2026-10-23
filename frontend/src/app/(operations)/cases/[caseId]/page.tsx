import { getCaseRepository } from "@/data/cases/case-repository-provider";
import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { ApiClientError, apiRequest } from "@/data/api/api-client";
import { resolutionSchema } from "@/features/resolution/contract";
import { updateCaseResolution } from "../../_actions/resolution";
import { practiceId, type PageSearch } from "@/features/practice/data";
import { PracticeWorkspacePage } from "@/features/practice/workspace-page";
import { apiInboxDraftRepository } from "@/data/connections/api-inbox-draft-repository";
import type { InboxDraftDelivery } from "@/domain/connections/connected-inbox";
import type { WorkflowControl } from "@/features/cases/components/case-decision-rail";
import { CaseWorkspace } from "@/features/cases/components/case-workspace";
import {
  caseWorkflowModes,
  caseWorkflowTarget,
} from "@/features/cases/case-workflow";
import { notFound } from "next/navigation";
import {
  addCaseEvidence,
  addCaseConversationEntry,
  analyzeCase,
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

export default async function CaseWorkspacePage({
  params,
  searchParams,
}: {
  params: Promise<{ caseId: string }>;
  searchParams: PageSearch;
}) {
  const { caseId } = await params;
  const search = await searchParams;
  const practice = practiceId(search.practice);
  if (practice) return <PracticeWorkspacePage sessionId={practice} area="cases" resourceId={caseId} tab={typeof search.tab === "string" ? search.tab : undefined}/>;
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
  const resolution = connected ? await apiRequest(`/api/cases/${encodeURIComponent(caseId)}/resolution`, resolutionSchema) : undefined;
  const inboxCase = workspace.case.sourceId.startsWith("inbox:");
  const savedResponseDraft =
    workspace.responseDraft?.source === "saved"
      ? workspace.responseDraft
      : null;
  let latestDraftDelivery: InboxDraftDelivery | null = null;
  if (connected && canManageCase && inboxCase && savedResponseDraft) {
    try {
      latestDraftDelivery = await apiInboxDraftRepository.getLatest(
        workspace.case.id,
        savedResponseDraft.version,
      );
    } catch (error) {
      if (!(error instanceof ApiClientError)) throw error;
    }
  }
  const replyChannel =
    workspace.request.channel === "webhook"
      ? "email"
      : workspace.request.channel;
  const workflowActions: WorkflowControl[] = connected
    ? caseWorkflowModes(workspace.availableCommands).map((mode) => ({
        mode,
        action:
          mode === "request_information"
            ? updateCaseWorkflow.bind(
                null,
                workspace.case.id,
                workspace.case.version,
                caseWorkflowTarget(mode),
              )
            : analyzeCase.bind(
                null,
                workspace.case.id,
                workspace.case.version,
                workspace.proposal?.version ?? 0,
                workspace.case.owner === null,
              ),
      }))
    : [];
  return (
    <CaseWorkspace
      workspace={workspace}
      resolution={resolution}
      resolutionAction={resolution && canManageCase ? updateCaseResolution.bind(null, caseId, resolution.version) : undefined}
      initialTab={search.tab === "resolution" ? "resolution" : "brief"}
      workflowActions={workflowActions}
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
              workspace.responseDraft?.editVersion ?? 0,
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
        connected && canManageCase && inboxCase && savedResponseDraft
          ? deliverResponseDraft.bind(
              null,
              workspace.case.id,
              savedResponseDraft.version,
            )
          : undefined
      }
      reconcileDraftAction={
        connected && canManageCase && inboxCase && savedResponseDraft
          ? reconcileResponseDraft
          : undefined
      }
      initialDraftDelivery={canManageCase ? latestDraftDelivery : null}
    />
  );
}
