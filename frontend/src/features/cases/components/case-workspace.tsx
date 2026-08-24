"use client";

import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { StatusLabel } from "@/components/ui/status-label";
import {
  WorkspaceTabs,
  type WorkspaceTabItem,
} from "@/components/ui/workspace-tabs";
import type { ServerCommand } from "@/data/commands/command-state";
import type {
  ActivityHistoryAction,
  ConversationHistoryAction,
} from "@/app/(operations)/_actions/cases";
import type { CaseWorkspace as CaseWorkspaceModel } from "@/domain/cases/case";
import {
  caseCategoryLabels,
  formatSla,
} from "@/features/cases/case-presentation";
import { resolveCaseWorkspaceStatus } from "@/features/cases/case-workspace-status";
import {
  ArrowLeft,
  Clock3,
  FileCheck2,
  FileText,
  History,
  MessageSquareText,
  UserRound,
} from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";
import { CaseDecisionBrief } from "./case-decision-brief";
import {
  CaseDecisionRail,
  type WorkflowControl,
} from "./case-decision-rail";
import type { InboxDraftAction } from "@/features/connections/action-contracts";
import { GmailDraftControl } from "@/features/connections/components/gmail-draft-control";
import type { InboxDraftDelivery } from "@/domain/connections/connected-inbox";

type WorkspaceTab = "brief" | "conversation" | "evidence" | "activity";

const tabs: readonly WorkspaceTabItem<WorkspaceTab>[] = [
  { id: "brief", label: "Decision brief", icon: FileText },
  { id: "conversation", label: "Conversation", icon: MessageSquareText },
  { id: "evidence", label: "Evidence", icon: FileCheck2 },
  { id: "activity", label: "Activity", icon: History },
];

const CaseConversationPanel = dynamic(
  () =>
    import("./case-conversation-panel").then(
      (module) => module.CaseConversationPanel,
    ),
  { loading: () => <DeferredPanelLoading label="conversation" /> },
);

const CaseEvidencePanel = dynamic(
  () =>
    import("./case-evidence-panel").then(
      (module) => module.CaseEvidencePanel,
    ),
  { loading: () => <DeferredPanelLoading label="evidence" /> },
);

const CaseActivityPanel = dynamic(
  () =>
    import("./case-activity-panel").then(
      (module) => module.CaseActivityPanel,
    ),
  { loading: () => <DeferredPanelLoading label="activity" /> },
);

function DeferredPanelLoading({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="grid min-h-[690px] place-items-center px-4 text-sm text-muted"
    >
      Loading {label}...
    </div>
  );
}

export function CaseWorkspace({
  workspace,
  workflowActions,
  prepareBriefAction,
  submitReviewAction,
  saveDraftAction,
  addReplyAction,
  addNoteAction,
  addEvidenceAction,
  loadConversationHistoryAction,
  loadActivityHistoryAction,
  deliverDraftAction,
  reconcileDraftAction,
  initialDraftDelivery,
}: {
  workspace: CaseWorkspaceModel;
  workflowActions?: readonly WorkflowControl[];
  prepareBriefAction?: ServerCommand;
  submitReviewAction?: ServerCommand;
  saveDraftAction?: ServerCommand;
  addReplyAction?: ServerCommand;
  addNoteAction?: ServerCommand;
  addEvidenceAction?: ServerCommand;
  loadConversationHistoryAction?: ConversationHistoryAction;
  loadActivityHistoryAction?: ActivityHistoryAction;
  deliverDraftAction?: InboxDraftAction;
  reconcileDraftAction?: InboxDraftAction;
  initialDraftDelivery?: InboxDraftDelivery | null;
}) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("brief");
  const status = resolveCaseWorkspaceStatus(workspace, initialDraftDelivery);

  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <header className="border-b border-border px-4 pt-4 sm:px-6 lg:px-7">
        <div className="mx-auto max-w-[1540px]">
          <nav
            aria-label="Breadcrumb"
            className="flex items-center gap-2 text-xs text-secondary"
          >
            <Link
              href="/cases"
              className="inline-flex items-center gap-1.5 font-medium text-info hover:underline"
            >
              <ArrowLeft aria-hidden="true" size={13} /> Cases
            </Link>
            <span aria-hidden="true">/</span>
            <span>{workspace.case.id}</span>
          </nav>

          <div className="mt-4 flex flex-col gap-4 pb-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <span className="font-mono text-sm font-semibold text-secondary">
                  {workspace.case.id}
                </span>
                <StatusLabel tone={status.tone}>{status.label}</StatusLabel>
                <span className="inline-flex items-center gap-1.5 text-xs text-secondary">
                  <Clock3 aria-hidden="true" size={14} /> SLA{" "}
                  {formatSla(workspace.case.slaMinutesRemaining)}
                </span>
              </div>
              <h1 className="mt-2 max-w-4xl text-[26px] font-semibold leading-tight text-primary sm:text-[30px]">
                {workspace.case.issue}
              </h1>
              <p className="mt-2 text-sm text-secondary">
                {caseCategoryLabels[workspace.case.category]} /{" "}
                {workspace.case.customer.name} /{" "}
                {workspace.case.externalReference}
              </p>
            </div>
            <div className="hidden text-right sm:block lg:pt-1">
              <p className="text-[11px] text-muted">Owner</p>
              <p className="mt-0.5 inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
                <UserRound aria-hidden="true" size={14} />{" "}
                {workspace.case.owner?.name ?? "Unassigned"}
              </p>
            </div>
          </div>

          <WorkspaceTabs
            items={tabs}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            label="Case workspace sections"
            panelIdPrefix="case-panel"
          />
        </div>
      </header>

      <div className="mx-auto max-w-[1540px]">
        {activeTab === "brief" ? (
          <div
            id="case-panel-brief"
            role="tabpanel"
            aria-labelledby="case-panel-tab-brief"
            className="grid xl:grid-cols-[minmax(0,1fr)_400px]"
          >
            <CaseDecisionBrief workspace={workspace} />
            <CaseDecisionRail
              workspace={workspace}
              workflowActions={workflowActions}
              prepareBriefAction={prepareBriefAction}
              submitReviewAction={submitReviewAction}
            />
          </div>
        ) : null}
        {activeTab === "conversation" ? (
          <div
            id="case-panel-conversation"
            role="tabpanel"
            aria-labelledby="case-panel-tab-conversation"
          >
            <CaseConversationPanel
              workspace={workspace}
              saveDraftAction={saveDraftAction}
              addReplyAction={addReplyAction}
              addNoteAction={addNoteAction}
              loadHistoryAction={loadConversationHistoryAction}
            />
            {workspace.responseDraft &&
            (deliverDraftAction || reconcileDraftAction || initialDraftDelivery) ? (
              <GmailDraftControl
                draftVersion={workspace.responseDraft.version}
                draftStatus={workspace.responseDraft.status}
                initialDelivery={initialDraftDelivery}
                deliverDraftAction={deliverDraftAction}
                reconcileDraftAction={reconcileDraftAction}
              />
            ) : null}
          </div>
        ) : null}
        {activeTab === "evidence" ? (
          <div
            id="case-panel-evidence"
            role="tabpanel"
            aria-labelledby="case-panel-tab-evidence"
          >
            <CaseEvidencePanel
              workspace={workspace}
              addEvidenceAction={addEvidenceAction}
            />
          </div>
        ) : null}
        {activeTab === "activity" ? (
          <div
            id="case-panel-activity"
            role="tabpanel"
            aria-labelledby="case-panel-tab-activity"
          >
            <CaseActivityPanel
              workspace={workspace}
              loadHistoryAction={loadActivityHistoryAction}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
