"use client";

import { EmptyState } from "@/components/ui/empty-state";
import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { OperationsPageHeader } from "@/components/ui/operations-page-header";
import { StatusLabel, type StatusTone } from "@/components/ui/status-label";
import type { ActionStatus, ActionSummary } from "@/domain/actions/action";
import { formatMoney, formatUpdatedAt } from "@/features/cases/case-presentation";
import { AlertOctagon, CheckCircle2, CirclePlay, RefreshCcw, Search, SlidersHorizontal } from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { useMemo, useState } from "react";

export const actionStatusPresentation: Record<ActionStatus, { label: string; tone: StatusTone }> = {
  ready: { label: "Ready", tone: "info" },
  running: { label: "Running", tone: "warning" },
  completed: { label: "Completed", tone: "success" },
  failed_safe: { label: "Failed safely", tone: "danger" },
  outcome_unknown: { label: "Outcome unknown", tone: "warning" },
  recovery_required: { label: "Recovery required", tone: "danger" },
};

const actionBlockerLabels = {
  permission: "Permission denied",
  duplicate: "Duplicate action",
  expired_approval: "Approval expired",
  connection_unavailable: "Connection unavailable",
  stale_proposal: "Resolution changed",
} as const;

export function ActionQueue({ actions, sourceLabel }: { actions: readonly ActionSummary[]; sourceLabel: string }) {
  const presentation = usePresentationPreferences();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ActionStatus | "all">("all");
  const rows = useMemo(() => { const normalized = query.trim().toLocaleLowerCase(); return actions.filter((item) => (!normalized || [item.id, item.caseId, item.label, item.target].join(" ").toLocaleLowerCase().includes(normalized)) && (status === "all" || item.status === status)); }, [actions, query, status]);
  const metrics = { ready: actions.filter((item) => item.status === "ready").length, running: actions.filter((item) => item.status === "running").length, completed: actions.filter((item) => item.status === "completed").length, recovery: actions.filter((item) => item.recoveryRequired).length };
  const emptyState = actions.length ? <EmptyState icon={SlidersHorizontal} title="No actions match this view" description="Reset the search and status filter to see all actions." action={<button type="button" onClick={() => { setQuery(""); setStatus("all"); }} className="text-sm font-semibold text-action hover:underline">Reset filters</button>} /> : <EmptyState icon={CirclePlay} title="No approved actions yet" description="Approved changes will appear here when they are ready to run or need recovery." />;
  return <div className="min-h-[calc(100vh-60px)] bg-surface"><OperationsPageHeader title="Actions" description="Approved changes, execution progress, and recovery work." meta={sourceLabel} /><section aria-label="Action summary" className="border-b border-border bg-canvas/55 px-4 sm:px-6 lg:px-7"><dl className="mx-auto grid max-w-[1540px] grid-cols-2 divide-x divide-border md:grid-cols-4">{[
    { label: "Ready", value: metrics.ready, icon: CirclePlay, tone: "text-info" }, { label: "Running", value: metrics.running, icon: RefreshCcw, tone: "text-warning" }, { label: "Completed", value: metrics.completed, icon: CheckCircle2, tone: "text-success" }, { label: "Needs recovery", value: metrics.recovery, icon: AlertOctagon, tone: "text-danger" },
  ].map((item) => { const Icon = item.icon; return <div key={item.label} className="flex min-h-[88px] items-center gap-3 px-3 first:pl-0 md:px-6 md:first:pl-0"><Icon aria-hidden="true" size={20} className={item.tone} /><div><dt className="text-xs text-secondary">{item.label}</dt><dd className="mt-0.5 text-xl font-semibold tabular-nums text-primary">{item.value}</dd></div></div>; })}</dl></section>
    <div className="mx-auto max-w-[1540px] px-4 py-6 sm:px-6 lg:px-7"><div className="flex flex-col gap-3 sm:flex-row"><label className="relative flex-1 sm:max-w-[620px]"><span className="sr-only">Search actions</span><Search aria-hidden="true" size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search actions, cases, or connected systems" className="h-10 w-full rounded-md border border-border pl-10 pr-3 text-sm outline-none focus:border-focus" /></label><label className="sm:ml-auto"><span className="sr-only">Filter action status</span><select value={status} onChange={(event) => setStatus(event.target.value as ActionStatus | "all")} className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-primary"><option value="all">All statuses</option>{Object.entries(actionStatusPresentation).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}</select></label></div>
      <div className="mt-5 overflow-hidden border border-border bg-surface"><div className="overflow-x-auto"><table className="w-full min-w-[1050px] border-collapse text-left"><caption className="sr-only">Approved support actions</caption><thead className="bg-canvas/65 text-[11px] font-semibold uppercase text-muted"><tr className="border-b border-border"><th className="px-4 py-3">Action</th><th className="px-3 py-3">Change</th><th className="px-3 py-3">Target</th><th className="px-3 py-3">Impact</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Attempts</th><th className="px-3 py-3">Owner</th><th className="px-4 py-3">Updated</th></tr></thead><tbody className="divide-y divide-border">{rows.map((item) => { const state = actionStatusPresentation[item.status]; return <tr key={item.id} className="group hover:bg-[#f2f8f7]"><td className="px-4 py-4"><Link href={`/actions/${item.id}`} className="font-mono text-xs font-semibold text-info hover:underline">{item.id}</Link><p className="mt-1 font-mono text-[11px] text-muted">{item.caseId}</p></td><td className="max-w-[260px] px-3 py-4"><Link href={`/actions/${item.id}`} className="text-sm font-semibold text-primary group-hover:text-action">{item.label}</Link></td><td className="px-3 py-4 text-sm text-secondary">{item.target}</td><td className="px-3 py-4 text-sm font-semibold text-primary">{item.impact ? formatMoney(item.impact.amount, item.impact.currency, presentation) : "No direct amount"}</td><td className="px-3 py-4"><StatusLabel tone={state.tone}>{state.label}</StatusLabel>{item.executionBlocker ? <p className="mt-2 text-[11px] font-medium text-danger">{actionBlockerLabels[item.executionBlocker]}</p> : null}{item.recoveryRequired ? <p className="mt-2 text-[11px] font-medium text-danger">Follow-up required</p> : null}</td><td className="px-3 py-4 text-sm tabular-nums text-secondary">{item.attemptCount}</td><td className="px-3 py-4 text-sm text-secondary">{item.owner?.name ?? "Unassigned"}</td><td className="px-4 py-4 text-xs text-muted">{formatUpdatedAt(item.updatedAt, presentation)}</td></tr>; })}</tbody></table></div>{!rows.length ? emptyState : <footer className="flex min-h-12 items-center border-t border-border px-4 text-xs text-muted">Showing {rows.length} of {actions.length} actions</footer>}</div>
    </div></div>;
}
