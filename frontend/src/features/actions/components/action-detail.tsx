"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { StatusLabel } from "@/components/ui/status-label";
import { CommandStatus } from "@/components/ui/command-status";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type { ActionDetail as ActionDetailModel } from "@/domain/actions/action";
import { formatMoney } from "@/features/cases/case-presentation";
import { formatDateTime } from "@/lib/presentation-format";
import { actionStatusPresentation } from "./action-queue";
import { AlertOctagon, ArrowLeft, CheckCircle2, CirclePlay, Clock3, FileSearch, RefreshCcw, ShieldCheck, TriangleAlert } from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { useActionState } from "react";

const blockerLabels = { permission: "Permission denied", duplicate: "Duplicate action detected", expired_approval: "Approval expired", connection_unavailable: "Connection unavailable", stale_proposal: "Recommended resolution changed" } as const;
const attemptOutcomeLabels = {
  running: "In progress",
  succeeded: "Completed",
  failed_before_change: "Stopped before any change",
  unknown: "Needs verification",
} as const;
const connectionHealthLabels = {
  healthy: "Ready",
  degraded: "Needs attention",
  unavailable: "Unavailable",
  not_configured: "Setup required",
} as const;

function CommandPanel({
  detail,
  commandAction,
}: {
  detail: ActionDetailModel;
  commandAction?: ServerCommand;
}) {
  const [state, formAction, pending] = useActionState(
    commandAction ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample data is read-only.",
      })),
    initialCommandState,
  );
  const commands = detail.availableCommands;
  return <aside aria-label="Action controls" className="border-t border-border bg-[#fbfcfc] px-5 py-6 xl:border-l xl:border-t-0 lg:px-7"><div className="xl:sticky xl:top-[76px]"><h2 className="text-base font-semibold text-primary">Available next step</h2>
    {detail.action.status === "outcome_unknown" ? <div className="mt-4 border border-warning/35 bg-warning-bg px-4 py-4"><TriangleAlert aria-hidden="true" size={20} className="text-warning" /><h3 className="mt-3 text-sm font-semibold text-primary">Do not retry this action</h3><p className="mt-2 text-xs leading-5 text-secondary">The change may already exist. Check the connected system using the same references before deciding what to do next.</p></div> : null}
    {detail.action.status === "failed_safe" ? <div className="mt-4 border border-danger/25 bg-danger-bg px-4 py-4"><AlertOctagon aria-hidden="true" size={20} className="text-danger" /><h3 className="mt-3 text-sm font-semibold text-primary">No connected-system change was made</h3><p className="mt-2 text-xs leading-5 text-secondary">The failure happened before the connected system accepted the request. A controlled retry can be allowed after the connection recovers.</p></div> : null}
    {detail.executionBlocker ? <div className="mt-4 border border-border px-4 py-3"><p className="text-xs font-semibold text-primary">Current blocker</p><p className="mt-1 text-sm text-secondary">{blockerLabels[detail.executionBlocker]}</p></div> : null}
    <form action={formAction} className="mt-5 space-y-2">
      {commands.includes("execute") ? <button type="submit" name="command" value="execute" disabled={!commandAction || pending} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-action text-sm font-semibold text-white hover:bg-action-strong disabled:cursor-not-allowed disabled:opacity-50"><CirclePlay aria-hidden="true" size={16} /> Execute approved action</button> : null}
      {commands.includes("retry_safe") ? <button type="submit" name="command" value="retry_safe" disabled={!commandAction || pending} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border border-action text-sm font-semibold text-action hover:bg-info-bg disabled:cursor-not-allowed disabled:opacity-50"><RefreshCcw aria-hidden="true" size={16} /> Retry after connection check</button> : null}
      {commands.includes("reconcile") ? <button type="submit" name="command" value="reconcile" disabled={!commandAction || pending} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-action text-sm font-semibold text-white hover:bg-action-strong disabled:cursor-not-allowed disabled:opacity-50"><FileSearch aria-hidden="true" size={16} /> Check target outcome</button> : null}
      {commands.includes("record_manual_outcome") || commands.includes("escalate") ? (
        <div className="space-y-3 border-t border-border pt-4">
          {commands.includes("record_manual_outcome") ? (
            <label className="grid gap-2 text-xs font-semibold text-primary">
              Verified outcome
              <select name="outcome" defaultValue="completed" className="h-10 rounded-md border border-border bg-surface px-3 text-sm font-normal">
                <option value="completed">Completed</option>
                <option value="not_completed">Not completed</option>
              </select>
            </label>
          ) : null}
          <label className="grid gap-2 text-xs font-semibold text-primary">
            Recovery reason
            <textarea name="reason" minLength={10} className="min-h-24 resize-y rounded-md border border-border bg-surface px-3 py-3 text-sm font-normal" />
          </label>
          {commands.includes("record_manual_outcome") ? <button type="submit" name="command" value="record_manual_outcome" disabled={!commandAction || pending} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border border-action text-sm font-semibold text-action disabled:cursor-not-allowed disabled:opacity-50"><ShieldCheck aria-hidden="true" size={16} /> Record verified outcome</button> : null}
          {commands.includes("escalate") ? <button type="submit" name="command" value="escalate" disabled={!commandAction || pending} className="inline-flex h-10 w-full items-center justify-center rounded-md border border-border text-sm font-semibold text-primary hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50">Escalate recovery</button> : null}
        </div>
      ) : null}
      <CommandStatus state={state} />
    </form>
    {!commands.length ? <p className="mt-4 text-sm leading-6 text-secondary">No further command is available for this action.</p> : null}
  </div></aside>;
}

export function ActionDetail({
  detail,
  commandAction,
}: {
  detail: ActionDetailModel;
  commandAction?: ServerCommand;
}) {
  const presentation = usePresentationPreferences();
  const action = detail.action; const state = actionStatusPresentation[action.status];
  return <div className="min-h-[calc(100vh-60px)] bg-surface"><header className="border-b border-border px-4 py-4 sm:px-6 lg:px-7"><div className="mx-auto max-w-[1540px]"><nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-secondary"><Link href="/actions" className="inline-flex items-center gap-1.5 font-medium text-info hover:underline"><ArrowLeft aria-hidden="true" size={13} /> Actions</Link><span>/</span><span>{action.id}</span></nav><div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-sm font-semibold text-secondary">{action.id}</span><StatusLabel tone={state.tone}>{state.label}</StatusLabel><span className="font-mono text-xs text-muted">{action.caseId}</span></div><h1 className="mt-2 text-[26px] font-semibold text-primary sm:text-[30px]">{action.label}</h1><p className="mt-2 text-sm text-secondary">Connected system: {action.target} / {action.impact ? formatMoney(action.impact.amount, action.impact.currency, presentation) : "No direct amount"}</p></div><Link href={`/cases/${action.caseId}`} className="text-sm font-semibold text-info hover:underline">View case</Link></div></div></header>
    <div className="mx-auto grid max-w-[1540px] xl:grid-cols-[minmax(0,1fr)_400px]"><div className="px-4 py-7 sm:px-6 lg:px-7">
      <section className="grid gap-px bg-border sm:grid-cols-3"><div className="bg-canvas px-4 py-4"><p className="text-xs text-muted">Expected outcome</p><p className="mt-2 text-sm font-medium leading-6 text-primary">{detail.expectedOutcome}</p></div><div className="bg-canvas px-4 py-4"><p className="text-xs text-muted">Observed outcome</p><p className="mt-2 text-sm font-medium leading-6 text-primary">{detail.observedOutcome ?? "Not available yet"}</p></div><div className="bg-canvas px-4 py-4"><p className="text-xs text-muted">Connected-system status</p><StatusLabel tone={detail.targetConnection.health === "healthy" ? "success" : detail.targetConnection.health === "degraded" ? "warning" : "danger"}>{connectionHealthLabels[detail.targetConnection.health]}</StatusLabel></div></section>
      <section aria-labelledby="authority-heading" className="border-b border-border py-7"><h2 id="authority-heading" className="text-base font-semibold text-primary">Approval details</h2><dl className="mt-4 grid gap-4 sm:grid-cols-2"><div><dt className="text-xs text-muted">Approved resolution</dt><dd className="mt-1 font-mono text-sm font-semibold text-primary">{detail.approvedProposal.id} v{detail.approvedProposal.version}</dd></div><div><dt className="text-xs text-muted">Review</dt><dd className="mt-1 font-mono text-sm font-semibold text-primary">{detail.approvedProposal.reviewId}</dd></div><div><dt className="text-xs text-muted">Approved by</dt><dd className="mt-1 text-sm font-semibold text-primary">{detail.authority.actor} / <span className="capitalize">{detail.authority.role}</span></dd></div><div><dt className="text-xs text-muted">Approval rule</dt><dd className="mt-1 text-sm font-semibold text-primary">{detail.authority.rule}</dd></div></dl></section>
      <section aria-labelledby="parameters-heading" className="border-b border-border py-7"><h2 id="parameters-heading" className="text-base font-semibold text-primary">Change details</h2><dl className="mt-4 divide-y divide-border border-y border-border">{Object.entries(detail.typedParameters).map(([label, value]) => <div key={label} className="flex items-start justify-between gap-4 py-3 text-sm"><dt className="capitalize text-secondary">{label.replaceAll("_", " ")}</dt><dd className="font-mono text-right text-primary">{value}</dd></div>)}</dl><p className="mt-3 text-xs text-muted">Safety reference: <span className="font-mono text-primary">{detail.idempotencyKey}</span></p></section>
      <section aria-labelledby="attempts-heading" className="border-b border-border py-7"><h2 id="attempts-heading" className="text-base font-semibold text-primary">Action history</h2>{detail.attempts.length ? <ol className="mt-4 divide-y divide-border border-y border-border">{detail.attempts.map((attempt) => <li key={attempt.id} className="grid gap-3 py-4 sm:grid-cols-[28px_minmax(0,1fr)_auto]"><span className={`grid size-7 place-items-center rounded-full ${attempt.outcome === "succeeded" ? "bg-success-bg text-success" : attempt.outcome === "unknown" ? "bg-warning-bg text-warning" : attempt.outcome === "failed_before_change" ? "bg-danger-bg text-danger" : "bg-info-bg text-info"}`}>{attempt.outcome === "succeeded" ? <CheckCircle2 size={14} /> : <Clock3 size={14} />}</span><div><p className="text-sm font-semibold text-primary">Attempt {attempt.number}: {attemptOutcomeLabels[attempt.outcome]}</p><p className="mt-1 text-xs leading-5 text-secondary">{attempt.detail}</p><p className="mt-1 text-[11px] text-muted">By {attempt.actor}</p></div><span className="font-mono text-[11px] text-muted">{attempt.id}</span></li>)}</ol> : <p className="mt-3 text-sm text-secondary">This approved action has not been attempted.</p>}</section>
      <section aria-labelledby="receipt-heading" className="py-7"><h2 id="receipt-heading" className="text-base font-semibold text-primary">Confirmation from connected system</h2>{detail.receipt ? <dl className="mt-4 grid gap-4 border border-success/25 bg-success-bg px-4 py-4 sm:grid-cols-3"><div><dt className="text-xs text-muted">Confirmation</dt><dd className="mt-1 font-mono text-sm text-primary">{detail.receipt.id}</dd></div><div><dt className="text-xs text-muted">System reference</dt><dd className="mt-1 font-mono text-sm text-primary">{detail.receipt.externalReference}</dd></div><div><dt className="text-xs text-muted">Recorded</dt><dd className="mt-1 text-sm text-primary">{formatDateTime(detail.receipt.recordedAt, presentation, { dateStyle: "medium", timeStyle: "short" })}</dd></div></dl> : <p className="mt-3 text-sm text-secondary">No confirmed result has been recorded by the connected system.</p>}</section>
    </div><CommandPanel detail={detail} commandAction={commandAction} /></div></div>;
}
