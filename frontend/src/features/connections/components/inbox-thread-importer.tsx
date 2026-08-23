"use client";

import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { CommandStatus } from "@/components/ui/command-status";
import {
  initialInboxImportState,
  initialInboxThreadsState,
  type InboxImportAction,
  type InboxImportState,
  type InboxThreadsAction,
} from "@/features/connections/action-contracts";
import { ArrowRight, Inbox, ListRestart } from "lucide-react";
import { useActionState } from "react";

function compactUtc(value: string): string {
  return `${value.replace("T", " ").slice(0, 16)} UTC`;
}

export function InboxThreadImporter({
  listThreadsAction,
  importThreadAction,
}: {
  listThreadsAction?: InboxThreadsAction;
  importThreadAction?: InboxImportAction;
}) {
  const [threadState, listAction, loading] = useActionState(
    listThreadsAction ??
      (async (state) => ({
        ...state,
        status: "error" as const,
        message: "You cannot view inbox conversations.",
      })),
    initialInboxThreadsState,
  );
  const submitImport = async (
    state: InboxImportState,
    formData: FormData,
  ): Promise<InboxImportState> => {
    const rawDueAt = String(formData.get("due_at") ?? "");
    const localDueAt = new Date(rawDueAt);
    if (rawDueAt && !Number.isNaN(localDueAt.getTime())) {
      formData.set("due_at", localDueAt.toISOString());
    }
    return (
      importThreadAction ??
      (async (current) => ({
        ...current,
        status: "error" as const,
        message: "You cannot import conversations.",
      }))
    )(state, formData);
  };
  const [importState, importAction, importing] = useActionState(
    submitImport,
    initialInboxImportState,
  );

  return (
    <section
      aria-labelledby="inbox-import-heading"
      className="min-w-0 max-w-full border-t border-border pt-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id="inbox-import-heading" className="text-sm font-semibold text-primary">
            Import a conversation
          </h3>
          <p className="mt-1 max-w-xl text-xs leading-5 text-muted">
            Conversations are loaded only when you request them. Choose one to
            create a case with its current messages.
          </p>
        </div>
        <form action={listAction}>
          {threadState.nextCursor ? (
            <input type="hidden" name="cursor" value={threadState.nextCursor} />
          ) : null}
          <button
            type="submit"
            disabled={!listThreadsAction || loading}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-primary hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ListRestart aria-hidden="true" size={14} />
            {loading
              ? "Loading..."
              : threadState.nextCursor
                ? "Show next page"
                : "Load conversations"}
          </button>
        </form>
      </div>

      <div className="mt-3">
        <CommandStatus state={threadState} />
      </div>

      {threadState.status === "success" && !threadState.items.length ? (
        <div className="mt-4 border border-border px-4 py-6 text-center">
          <Inbox aria-hidden="true" size={20} className="mx-auto text-muted" />
          <p className="mt-2 text-sm font-medium text-primary">
            No recent conversations found
          </p>
          <p className="mt-1 text-xs text-muted">
            Nothing was imported. You can update the inbox and check again.
          </p>
        </div>
      ) : null}

      {threadState.items.length ? (
        <form
          action={importAction}
          className="mt-4 min-w-0 max-w-full border border-border"
        >
          <fieldset className="min-w-0 divide-y divide-border">
            <legend className="sr-only">Choose a conversation</legend>
            {threadState.items.map((thread, index) => (
              <label
                key={thread.providerThreadId}
                className="flex min-w-0 w-full cursor-pointer items-start gap-3 px-4 py-3 hover:bg-surface-subtle"
              >
                <input
                  type="radio"
                  name="provider_thread_id"
                  value={thread.providerThreadId}
                  required
                  defaultChecked={index === 0}
                  className="mt-1"
                />
                <span className="min-w-0 flex-1 overflow-hidden">
                  <span
                    title={thread.subject}
                    className="block truncate text-sm font-medium text-primary"
                  >
                    {thread.subject}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted">
                    Latest message {compactUtc(thread.latestMessageAt)}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>

          <div className="grid min-w-0 gap-3 border-t border-border bg-canvas/45 p-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="min-w-0 text-xs font-medium text-secondary">
              Case type
              <select name="category" defaultValue="service_exception" className="mt-1 h-10 w-full min-w-0 rounded-md border border-border bg-surface px-3 text-sm text-primary">
                <option value="service_exception">Service issue</option>
                <option value="billing_dispute">Billing dispute</option>
                <option value="refund_request">Refund request</option>
                <option value="account_access">Account access</option>
              </select>
            </label>
            <label className="min-w-0 text-xs font-medium text-secondary">
              Urgency
              <select name="urgency" defaultValue="medium" className="mt-1 h-10 w-full min-w-0 rounded-md border border-border bg-surface px-3 text-sm text-primary">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </label>
            <label className="min-w-0 text-xs font-medium text-secondary">
              Risk
              <select name="risk" defaultValue="medium" className="mt-1 h-10 w-full min-w-0 rounded-md border border-border bg-surface px-3 text-sm text-primary">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label className="min-w-0 text-xs font-medium text-secondary">
              Due date
              <input name="due_at" type="datetime-local" required className="mt-1 h-10 w-full min-w-0 rounded-md border border-border bg-surface px-3 text-sm text-primary" />
            </label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3">
            <p className="text-xs text-muted">
              The original Gmail conversation remains unchanged.
            </p>
            <button
              type="submit"
              disabled={!importThreadAction || importing}
              className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {importing ? "Importing..." : "Create case"}
              <ArrowRight aria-hidden="true" size={14} />
            </button>
          </div>
        </form>
      ) : null}

      <div className="mt-3">
        <CommandStatus state={importState} />
      </div>
      {importState.caseId ? (
        <Link href={`/cases/${importState.caseId}`} className="mt-3 inline-flex text-sm font-semibold text-action hover:underline">
          Open {importState.caseId}
        </Link>
      ) : null}
    </section>
  );
}
