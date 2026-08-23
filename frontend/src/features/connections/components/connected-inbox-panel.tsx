"use client";

import { CommandStatus } from "@/components/ui/command-status";
import { StatusLabel } from "@/components/ui/status-label";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type {
  ConnectedInbox,
  InboxConnectionStatus,
} from "@/domain/connections/connected-inbox";
import { resolveConnectedInboxStatus } from "@/domain/connections/connected-inbox";
import type {
  InboxControlAction,
  InboxImportAction,
  InboxThreadsAction,
} from "@/features/connections/action-contracts";
import { FilePenLine, Inbox, LockKeyhole } from "lucide-react";
import { useActionState } from "react";
import { InboxConnectionControls } from "./inbox-connection-controls";
import { InboxThreadImporter } from "./inbox-thread-importer";

const statusPresentation = {
  ready: { label: "Ready", tone: "success" },
  needs_attention: { label: "Needs attention", tone: "warning" },
  reconnect_required: { label: "Sign in again", tone: "danger" },
  setup_required: { label: "Setup required", tone: "neutral" },
} as const;

function StartInboxConnection({
  action,
  reconnect = false,
  includeDrafts = false,
}: {
  action?: ServerCommand;
  reconnect?: boolean;
  includeDrafts?: boolean;
}) {
  const [state, formAction, pending] = useActionState(
    action ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Only a workspace administrator can connect an inbox.",
      })),
    initialCommandState,
  );
  return (
    <div>
      <form action={formAction}>
        <input
          type="hidden"
          name="include_drafts"
          value={includeDrafts ? "true" : "false"}
        />
        <button
          type="submit"
          disabled={!action || pending}
          className="inline-flex h-10 items-center rounded-md bg-action px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending
            ? "Opening secure sign-in..."
            : includeDrafts && !reconnect
              ? "Add draft access"
            : reconnect
              ? "Sign in again"
              : "Connect Gmail"}
        </button>
      </form>
      <div className="mt-3">
        <CommandStatus state={state} />
      </div>
    </div>
  );
}

export function ConnectedInboxPanel({
  inbox,
  inboxStatus,
  statusLoadError,
  connectedWorkspace,
  startAuthorizationAction,
  listThreadsAction,
  importThreadAction,
  syncAction,
  pauseAction,
  resumeAction,
  disconnectAction,
}: {
  inbox: ConnectedInbox | null;
  inboxStatus?: InboxConnectionStatus | null;
  statusLoadError?: string | null;
  connectedWorkspace: boolean;
  startAuthorizationAction?: ServerCommand;
  listThreadsAction?: InboxThreadsAction;
  importThreadAction?: InboxImportAction;
  syncAction?: InboxControlAction;
  pauseAction?: InboxControlAction;
  resumeAction?: InboxControlAction;
  disconnectAction?: InboxControlAction;
}) {
  const effectiveStatus = inbox
    ? resolveConnectedInboxStatus(inbox.status, inboxStatus)
    : undefined;
  const status = effectiveStatus ? statusPresentation[effectiveStatus] : null;
  const accountAddress = inboxStatus?.accountAddress ?? inbox?.accountAddress;
  const canRead = inboxStatus
    ? inboxStatus.capabilities.includes("conversation_read")
    : (inbox?.canReadConversations ?? false);
  const canCreateDrafts = inboxStatus
    ? inboxStatus.capabilities.includes("draft_create")
    : (inbox?.canCreateDrafts ?? false);

  return (
    <section aria-labelledby="connected-inbox-heading" className="border border-border bg-surface px-5 py-5 sm:px-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-md bg-info-bg text-info">
              <Inbox aria-hidden="true" size={18} />
            </span>
            <div>
              <h2 id="connected-inbox-heading" className="text-base font-semibold text-primary">
                Connected inbox
              </h2>
              <p className="mt-0.5 text-xs text-muted">
                Bring selected customer conversations into governed cases.
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-3 text-sm text-secondary sm:grid-cols-2">
            <p className="flex gap-2">
              <LockKeyhole aria-hidden="true" size={16} className="mt-0.5 shrink-0 text-success" />
              Reads conversations to import and keep connected cases current.
            </p>
            <p className="flex gap-2">
              <FilePenLine aria-hidden="true" size={16} className="mt-0.5 shrink-0 text-success" />
              Creates Gmail drafts for review. Nothing is sent automatically.
            </p>
          </div>
        </div>
        {inbox && status ? (
          <div className="flex items-center gap-3 lg:justify-end">
            <div className="text-right">
              <p className="text-sm font-semibold text-primary">{accountAddress}</p>
              <p className="mt-0.5 text-xs text-muted">
                {canCreateDrafts ? "Conversation and draft access" : "Conversation access only"}
              </p>
            </div>
            <StatusLabel tone={status.tone}>{status.label}</StatusLabel>
          </div>
        ) : null}
      </div>

      {statusLoadError ? (
        <p role="alert" className="mt-5 border border-warning/30 bg-warning-bg px-3 py-3 text-xs text-warning">
          {statusLoadError}
        </p>
      ) : null}

      {inboxStatus ? (
        <dl className="mt-5 grid gap-3 border-y border-border py-4 text-xs sm:grid-cols-3">
          <div>
            <dt className="text-muted">Update mode</dt>
            <dd className="mt-1 font-medium capitalize text-primary">{inboxStatus.importMode}</dd>
          </div>
          <div>
            <dt className="text-muted">Last successful update</dt>
            <dd className="mt-1 font-medium text-primary">
              {inboxStatus.lastSuccessfulSyncAt
                ? `${inboxStatus.lastSuccessfulSyncAt.replace("T", " ").slice(0, 16)} UTC`
                : "Not yet"}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Latest update</dt>
            <dd className="mt-1 font-medium text-primary">
              {inboxStatus.lastErrorCode ? "Needs attention" : "No reported issue"}
            </dd>
          </div>
        </dl>
      ) : null}

      {!inbox ? (
        <div className="mt-6 flex flex-col gap-4 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-2xl text-sm leading-6 text-secondary">
            Connect a dedicated work inbox. Google will show the exact access
            requested before anything is connected.
          </p>
          <StartInboxConnection
            action={connectedWorkspace ? startAuthorizationAction : undefined}
          />
        </div>
      ) : null}

      {effectiveStatus === "reconnect_required" || effectiveStatus === "setup_required" ? (
        <div className="mt-6 flex flex-col gap-4 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-2xl text-sm leading-6 text-secondary">
            Access is no longer current. Sign in again before loading conversations or creating drafts.
          </p>
          <StartInboxConnection
            action={startAuthorizationAction}
            reconnect
            includeDrafts={canCreateDrafts}
          />
        </div>
      ) : null}

      {inbox && effectiveStatus === "ready" && !canCreateDrafts && startAuthorizationAction ? (
        <div className="mt-6 flex flex-col gap-4 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-2xl text-sm leading-6 text-secondary">
            Conversation access is active. Add draft access separately only when
            your team is ready to create reviewed replies in Gmail.
          </p>
          <StartInboxConnection
            action={startAuthorizationAction}
            includeDrafts
          />
        </div>
      ) : null}

      {inbox && effectiveStatus && ["ready", "needs_attention"].includes(effectiveStatus) ? (
        <div className="mt-6 space-y-5">
          <InboxThreadImporter
            listThreadsAction={canRead ? listThreadsAction : undefined}
            importThreadAction={importThreadAction}
          />
          <InboxConnectionControls
            syncAction={syncAction}
            pauseAction={pauseAction}
            resumeAction={resumeAction}
            disconnectAction={disconnectAction}
            initiallyPaused={inboxStatus?.importMode === "paused"}
          />
        </div>
      ) : null}
    </section>
  );
}
