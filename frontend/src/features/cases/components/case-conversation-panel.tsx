"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { CommandStatus } from "@/components/ui/command-status";
import type { ConversationHistoryAction } from "@/app/(operations)/_actions/cases";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type {
  CaseConversationMessage,
  CaseWorkspace,
} from "@/domain/cases/case";
import { caseCategoryLabels } from "@/features/cases/case-presentation";
import { ChevronUp, NotebookPen, Save, Send } from "lucide-react";
import {
  useActionState,
  useRef,
  useState,
  useTransition,
  type KeyboardEvent,
} from "react";
import { formatCaseDateTime } from "./case-workspace-format";

function EntryControl({
  action,
  body,
  mode,
}: {
  action?: ServerCommand;
  body: string;
  mode: "reply" | "note";
}) {
  const [state, formAction, pending] = useActionState(
    action ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample data is read-only.",
      })),
    initialCommandState,
  );
  const Icon = mode === "reply" ? Send : NotebookPen;
  const label = mode === "reply" ? "Add reply" : "Add internal note";

  return (
    <div>
      <form action={formAction}>
        <input type="hidden" name="body" value={body} />
        <button
          type="submit"
          disabled={!action || pending || !body.trim()}
          className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Icon aria-hidden="true" size={15} />
          {pending ? "Adding..." : label}
        </button>
      </form>
      <CommandStatus state={state} />
    </div>
  );
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function CaseConversationPanel({
  workspace,
  saveDraftAction,
  addReplyAction,
  addNoteAction,
  loadHistoryAction,
}: {
  workspace: CaseWorkspace;
  saveDraftAction?: ServerCommand;
  addReplyAction?: ServerCommand;
  addNoteAction?: ServerCommand;
  loadHistoryAction?: ConversationHistoryAction;
}) {
  const presentation = usePresentationPreferences();
  const [mode, setMode] = useState<"reply" | "note">("reply");
  const [messages, setMessages] = useState<CaseConversationMessage[]>(
    workspace.conversation.messages,
  );
  const [historyCursor, setHistoryCursor] = useState(
    workspace.collections.messages.nextCursor,
  );
  const [messageTotal, setMessageTotal] = useState(
    workspace.collections.messages.total,
  );
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyPending, startHistoryTransition] = useTransition();
  const composerTabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const initialDraft =
    workspace.responseDraft?.source === "placeholder"
      ? null
      : workspace.responseDraft;
  const [draft, setDraft] = useState(initialDraft?.body ?? "");
  const [note, setNote] = useState("");
  const [subject, setSubject] = useState(
    initialDraft?.subject ?? `${workspace.case.id} support update`,
  );
  const composerModes = ["reply", "note"] as const;

  function handleComposerTabKey(
    event: KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      const direction = event.key === "ArrowRight" ? 1 : -1;
      nextIndex =
        (currentIndex + direction + composerModes.length) %
        composerModes.length;
    }
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = composerModes.length - 1;
    if (nextIndex === null) return;

    event.preventDefault();
    const nextMode = composerModes[nextIndex];
    if (!nextMode) return;
    setMode(nextMode);
    composerTabRefs.current[nextIndex]?.focus();
  }
  const [draftState, saveDraftFormAction, savingDraft] = useActionState(
    saveDraftAction ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample data is read-only.",
      })),
    initialCommandState,
  );
  const customerInitials = initials(workspace.case.customer.name);
  const canWrite = Boolean(
    saveDraftAction || addReplyAction || addNoteAction,
  );

  function loadEarlierMessages() {
    if (!loadHistoryAction || !historyCursor) return;
    startHistoryTransition(async () => {
      const result = await loadHistoryAction(historyCursor);
      if (result.status === "error") {
        setHistoryError(result.message);
        return;
      }
      setMessages((current) => {
        const currentIds = new Set(current.map((message) => message.id));
        return [
          ...result.items.filter((message) => !currentIds.has(message.id)),
          ...current,
        ];
      });
      setHistoryCursor(result.nextCursor);
      setMessageTotal(result.total);
      setHistoryError(null);
    });
  }

  return (
    <div className="grid min-h-[690px] lg:grid-cols-[minmax(0,1fr)_320px]">
      <section
        aria-labelledby="conversation-heading"
        className="border-b border-border px-4 py-6 sm:px-6 lg:border-b-0 lg:border-r lg:px-7"
      >
        <div>
          <h2
            id="conversation-heading"
            className="text-base font-semibold text-primary"
          >
            Customer conversation
          </h2>
          <p className="mt-1 text-xs capitalize text-muted">
            {workspace.request.channel} channel /{" "}
            {messages.length === messageTotal
              ? `${messageTotal} messages`
              : `${messages.length} of ${messageTotal} messages shown`}
          </p>
        </div>

        {loadHistoryAction && historyCursor ? (
          <button
            type="button"
            onClick={loadEarlierMessages}
            disabled={historyPending}
            className="mt-5 inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-primary hover:bg-surface-subtle disabled:cursor-wait disabled:opacity-60"
          >
            <ChevronUp aria-hidden="true" size={15} />
            {historyPending ? "Loading..." : "Load earlier messages"}
          </button>
        ) : null}
        {historyError ? (
          <p role="alert" className="mt-3 text-xs text-danger">
            {historyError}
          </p>
        ) : null}

        <div className="mt-6 space-y-5">
          {messages.map((message) => {
            const customer = message.authorType === "customer";
            return (
              <article
                key={message.id}
                className={`border-l-2 pl-4 ${
                  message.internal
                    ? "border-warning bg-warning-bg/45 py-3 pr-3"
                    : customer
                      ? "border-border"
                      : "border-info"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`grid size-8 place-items-center rounded-full text-xs font-bold ${
                      message.internal
                        ? "bg-warning-bg text-warning"
                        : customer
                          ? "bg-info-bg text-info"
                          : "bg-success-bg text-success"
                    }`}
                  >
                    {initials(message.authorName)}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-primary">
                      {message.authorName}
                      {message.internal ? (
                        <span className="ml-2 text-xs font-medium text-warning">
                          Internal note
                        </span>
                      ) : null}
                    </p>
                    <time
                      className="text-[11px] text-muted"
                      dateTime={message.createdAt}
                    >
                      {formatCaseDateTime(message.createdAt, presentation)}
                    </time>
                  </div>
                </div>
                <p className="mt-4 whitespace-pre-line text-sm leading-7 text-secondary">
                  {message.body}
                </p>
              </article>
            );
          })}
        </div>

        {canWrite ? (
        <div className="mt-8 border border-border bg-surface">
          <div
            role="tablist"
            aria-label="Conversation composer"
            className="flex h-11 items-center gap-5 border-b border-border px-4 text-xs font-semibold"
          >
            <button
              ref={(element) => {
                composerTabRefs.current[0] = element;
              }}
              id="composer-tab-reply"
              type="button"
              role="tab"
              aria-selected={mode === "reply"}
              aria-controls="composer-panel-reply"
              tabIndex={mode === "reply" ? 0 : -1}
              onClick={() => setMode("reply")}
              onKeyDown={(event) => handleComposerTabKey(event, 0)}
              className={`flex h-11 items-center border-b-2 ${
                mode === "reply"
                  ? "border-action text-action"
                  : "border-transparent text-secondary"
              }`}
            >
              Reply
            </button>
            <button
              ref={(element) => {
                composerTabRefs.current[1] = element;
              }}
              id="composer-tab-note"
              type="button"
              role="tab"
              aria-selected={mode === "note"}
              aria-controls="composer-panel-note"
              tabIndex={mode === "note" ? 0 : -1}
              onClick={() => setMode("note")}
              onKeyDown={(event) => handleComposerTabKey(event, 1)}
              className={`flex h-11 items-center border-b-2 ${
                mode === "note"
                  ? "border-action text-action"
                  : "border-transparent text-secondary"
              }`}
            >
              Internal note
            </button>
          </div>

          {mode === "reply" ? (
            <div
              id="composer-panel-reply"
              role="tabpanel"
              aria-labelledby="composer-tab-reply"
            >
              <form action={saveDraftFormAction}>
                <label className="block border-b border-border px-4 py-3">
                  <span className="sr-only">Response subject</span>
                  <input
                    name="subject"
                    value={subject}
                    onChange={(event) => setSubject(event.target.value)}
                    className="w-full text-sm font-semibold text-primary outline-none"
                  />
                </label>
                <textarea
                  name="body"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  aria-label="Response draft"
                  className="min-h-40 w-full resize-y px-4 py-4 text-sm leading-6 text-primary outline-none"
                />
                <div className="flex items-center justify-between border-t border-border px-3 py-3">
                  <span className="text-xs text-muted">Customer-facing reply</span>
                  <button
                    type="submit"
                    disabled={!saveDraftAction || savingDraft}
                    className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-primary hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Save aria-hidden="true" size={15} />
                    {savingDraft ? "Saving..." : "Save draft"}
                  </button>
                </div>
              </form>
              <div className="flex flex-wrap items-start justify-between gap-3 border-t border-border px-3 py-3">
                <p className="max-w-lg text-xs leading-5 text-muted">
                  Adding a reply records it in this case. Delivery to an external
                  support tool depends on its connection.
                </p>
                <EntryControl
                  action={addReplyAction}
                  body={draft}
                  mode="reply"
                />
              </div>
              <div className="px-3 pb-3">
                <CommandStatus state={draftState} />
              </div>
            </div>
          ) : (
            <div
              id="composer-panel-note"
              role="tabpanel"
              aria-labelledby="composer-tab-note"
            >
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                aria-label="Internal note"
                placeholder="Add context for other workspace members"
                className="min-h-40 w-full resize-y px-4 py-4 text-sm leading-6 text-primary outline-none"
              />
              <div className="flex flex-wrap items-start justify-between gap-3 border-t border-border px-3 py-3">
                <p className="max-w-lg text-xs leading-5 text-muted">
                  Internal notes are visible to workspace members, not customers.
                </p>
                <EntryControl
                  action={addNoteAction}
                  body={note}
                  mode="note"
                />
              </div>
            </div>
          )}
        </div>
        ) : (
          <p className="mt-8 border border-border bg-canvas/45 px-4 py-4 text-sm text-secondary">
            You can read this conversation, but your role cannot add replies,
            notes, or drafts.
          </p>
        )}
      </section>

      <aside aria-label="Customer context" className="px-4 py-6 sm:px-6">
        <h2 className="text-sm font-semibold text-primary">Customer</h2>
        <div className="mt-4 flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-full bg-info-bg text-xs font-bold text-info">
            {customerInitials}
          </span>
          <div>
            <p className="text-sm font-semibold text-primary">
              {workspace.case.customer.name}
            </p>
            <p className="text-xs text-secondary">
              {workspace.customer.contact}
            </p>
          </div>
        </div>
        <dl className="mt-5 divide-y divide-border border-y border-border">
          {[
            ["Customer ID", workspace.customer.id],
            ["Tier", workspace.customer.tier],
            ["Locale", workspace.customer.locale],
            ["Reference", workspace.case.externalReference],
            ["Category", caseCategoryLabels[workspace.case.category]],
          ].map(([label, value]) => (
            <div
              key={label}
              className="flex items-start justify-between gap-4 py-3 text-xs"
            >
              <dt className="text-muted">{label}</dt>
              <dd className="text-right font-medium capitalize text-primary">
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </aside>
    </div>
  );
}
