"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { StatusLabel } from "@/components/ui/status-label";
import { CommandStatus } from "@/components/ui/command-status";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type { ReviewDecision, ReviewSnapshot } from "@/domain/reviews/review";
import { formatMoney } from "@/features/cases/case-presentation";
import { AlertOctagon, ArrowLeft, Check, CheckCircle2, Clock3, LockKeyhole, MessageSquareWarning, ShieldCheck, XCircle } from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { useActionState, useState } from "react";

const decisions: readonly { id: ReviewDecision; label: string; icon: typeof Check; className: string }[] = [
  { id: "approve", label: "Approve", icon: Check, className: "bg-action text-white hover:bg-action-strong" },
  { id: "request_changes", label: "Request changes", icon: MessageSquareWarning, className: "border border-warning/40 text-warning hover:bg-warning-bg" },
  { id: "reject", label: "Reject", icon: XCircle, className: "border border-danger/35 text-danger hover:bg-danger-bg" },
  { id: "escalate", label: "Escalate", icon: AlertOctagon, className: "border border-border text-primary hover:bg-surface-subtle" },
];

function SnapshotVersions({ snapshot }: { snapshot: ReviewSnapshot }) {
  return <dl className="grid gap-px bg-border sm:grid-cols-4">{[["Case version", snapshot.caseVersion], ["Resolution version", `v${snapshot.proposal.version}`], ["Policy guidance", `${snapshot.evidence.length} items`], ["Risk checks", `${snapshot.risks.length} checks`]].map(([label, value]) => <div key={label} className="bg-canvas px-4 py-3"><dt className="text-[11px] uppercase text-muted">{label}</dt><dd className="mt-1 text-xs font-semibold text-primary">{value}</dd></div>)}</dl>;
}

function DecisionPanel({
  snapshot,
  reserveAction,
  decideAction,
}: {
  snapshot: ReviewSnapshot;
  reserveAction?: ServerCommand;
  decideAction?: ServerCommand;
}) {
  const blocked = snapshot.review.snapshotFreshness.status === "stale";
  const terminal = [
    "approved",
    "changes_requested",
    "rejected",
    "escalated",
  ].includes(snapshot.review.status);
  const heldByOther =
    snapshot.review.reservation !== null &&
    snapshot.availableDecisions.length === 0;
  const reservedByMe =
    snapshot.review.reservation !== null &&
    snapshot.availableDecisions.length > 0;
  const [reason, setReason] = useState("");
  const [reserveState, reserveFormAction, reserving] = useActionState(
    reserveAction ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample data is read-only.",
      })),
    initialCommandState,
  );
  const [decisionState, decisionFormAction, deciding] = useActionState(
    decideAction ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample data is read-only.",
      })),
    initialCommandState,
  );

  if (terminal) return <aside aria-label="Decision controls" className="border-t border-border bg-[#fbfcfc] px-5 py-6 xl:border-l xl:border-t-0 lg:px-7"><div className="xl:sticky xl:top-[76px]"><CheckCircle2 aria-hidden="true" size={24} className="text-success" /><h2 className="mt-4 text-lg font-semibold text-primary">Review complete</h2><p className="mt-3 text-sm leading-6 text-secondary">This review is {snapshot.review.status.replaceAll("_", " ")}. Its decision and case version are preserved in the activity history.</p>{blocked ? <div className="mt-5 border border-warning/30 bg-warning-bg px-4 py-3 text-sm text-warning">The source case changed after this decision. The recorded review remains unchanged.</div> : null}<Link href={`/cases/${snapshot.review.caseId}`} className="mt-5 inline-flex h-10 items-center justify-center rounded-md border border-border px-4 text-sm font-semibold text-primary hover:bg-surface-subtle">Open source case</Link></div></aside>;
  if (blocked) return <aside aria-label="Decision controls" className="border-t border-border bg-[#fffafa] px-5 py-6 xl:border-l xl:border-t-0 lg:px-7"><div className="xl:sticky xl:top-[76px]"><AlertOctagon aria-hidden="true" size={24} className="text-danger" /><h2 className="mt-4 text-lg font-semibold text-primary">Decision blocked</h2><p className="mt-3 text-sm leading-6 text-secondary">{snapshot.review.snapshotFreshness.reason ?? "This review is unavailable for a decision."}</p><div className="mt-5 border border-danger/25 bg-danger-bg px-4 py-3 text-sm text-danger">The case changed after this review was submitted. Open the current case and submit it for review again.</div><Link href={`/cases/${snapshot.review.caseId}`} className="mt-5 inline-flex h-10 items-center justify-center rounded-md border border-border px-4 text-sm font-semibold text-primary hover:bg-surface-subtle">Open current case</Link></div></aside>;

  return (
    <aside aria-label="Decision controls" className="border-t border-border bg-[#fbfcfc] px-5 py-6 xl:border-l xl:border-t-0 lg:px-7"><div className="xl:sticky xl:top-[76px]">
      <div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-full bg-success-bg text-success"><ShieldCheck aria-hidden="true" size={19} /></span><div><h2 className="text-base font-semibold text-primary">Your approval rights</h2><p className="text-xs capitalize text-secondary">{snapshot.approvalRule.requiredRole}</p></div></div>
      <p className="mt-5 text-sm leading-6 text-secondary">{snapshot.approvalRule.explanation}</p>
      {heldByOther ? <div className="mt-5 border border-warning/30 bg-warning-bg px-4 py-3 text-sm text-warning">Reserved by {snapshot.review.reservation?.reviewerName}. You cannot decide this review.</div> : null}
      {!heldByOther && !reservedByMe && reserveAction ? (
        <form action={reserveFormAction} className="mt-6 space-y-3">
          <button
            type="submit"
            disabled={!reserveAction || reserving}
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-action text-sm font-semibold text-white hover:bg-action-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            <LockKeyhole aria-hidden="true" size={16} />
            {reserving ? "Reserving..." : "Reserve review"}
          </button>
          <CommandStatus state={reserveState} />
        </form>
      ) : null}
      {!heldByOther && !reservedByMe && !reserveAction ? (
        <p className="mt-6 border border-border bg-canvas/45 px-4 py-3 text-sm text-secondary">
          You can inspect this review, but your role cannot reserve or decide it.
        </p>
      ) : null}
      {reservedByMe ? (
        <form action={decisionFormAction} className="mt-6">
          <div role="status" className="mb-4 border border-info/20 bg-info-bg px-3 py-3 text-xs text-info">
            Reserved to {snapshot.review.reservation?.reviewerName}. Decisions apply to this exact case version.
          </div>
          <label className="grid gap-2 text-xs font-semibold text-primary">
            Reason for decision
            <textarea
              name="reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Explain why this decision is appropriate"
              className="min-h-28 resize-y rounded-md border border-border bg-surface px-3 py-3 text-sm font-normal leading-6 outline-none focus:border-focus"
            />
          </label>
          <p className={`mt-2 text-xs ${reason.trim().length >= 10 ? "text-success" : "text-muted"}`}>
            At least 10 characters are required.
          </p>
          <div className="mt-5 grid grid-cols-2 gap-2">
            {decisions
              .filter((item) => snapshot.availableDecisions.includes(item.id))
              .map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="submit"
                    name="decision"
                    value={item.id}
                    disabled={!decideAction || deciding || reason.trim().length < 10}
                    className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-3 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${item.className}`}
                  >
                    <Icon aria-hidden="true" size={15} />
                    {item.label}
                  </button>
                );
              })}
          </div>
          <div className="mt-4">
            <CommandStatus state={decisionState} />
          </div>
        </form>
      ) : null}
    </div></aside>
  );
}

export function ReviewWorkspace({
  snapshot,
  reserveAction,
  decideAction,
}: {
  snapshot: ReviewSnapshot;
  reserveAction?: ServerCommand;
  decideAction?: ServerCommand;
}) {
  const presentation = usePresentationPreferences();
  const review = snapshot.review;
  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <header className="border-b border-border bg-surface px-4 py-4 sm:px-6 lg:px-7"><div className="mx-auto max-w-[1540px]"><nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-secondary"><Link href="/reviews" className="inline-flex items-center gap-1.5 font-medium text-info hover:underline"><ArrowLeft aria-hidden="true" size={13} /> Reviews</Link><span>/</span><span>{review.id}</span></nav><div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-sm font-semibold text-secondary">{review.id}</span><StatusLabel tone={review.snapshotFreshness.status === "current" ? "success" : "danger"}>{review.snapshotFreshness.status === "current" ? "Case version current" : "Case changed"}</StatusLabel><span className="font-mono text-xs text-muted">{review.caseId}</span></div><h1 className="mt-2 text-[26px] font-semibold leading-tight text-primary sm:text-[30px]">Authorize: {snapshot.proposal.outcome}</h1><p className="mt-2 text-sm text-secondary">Submitted by {review.submittedBy.name} / Resolution {snapshot.proposal.id} v{snapshot.proposal.version}</p></div><Link href={`/cases/${review.caseId}`} className="text-sm font-semibold text-info hover:underline">View source case</Link></div></div></header>
      <SnapshotVersions snapshot={snapshot} />
      <div className="mx-auto grid max-w-[1540px] xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="px-4 py-7 sm:px-6 lg:px-7">
          <section className="border-b border-border pb-7"><p className="text-xs font-semibold uppercase text-muted">Recommended resolution</p><h2 className="mt-3 text-xl font-semibold text-primary">{snapshot.proposal.outcome}</h2>{snapshot.proposal.impact ? <p className="mt-3 text-2xl font-semibold text-success">{formatMoney(snapshot.proposal.impact.amount, snapshot.proposal.impact.currency, presentation)}</p> : <p className="mt-3 text-sm text-secondary">No direct financial amount</p>}<p className="mt-4 max-w-4xl text-sm leading-7 text-secondary">{snapshot.proposal.rationale}</p><div className="mt-4 border-l-2 border-warning bg-warning-bg/45 px-4 py-3"><p className="text-xs font-semibold text-warning">What is still uncertain</p><p className="mt-1 text-sm leading-6 text-secondary">{snapshot.proposal.uncertainty}</p></div></section>
          <section aria-labelledby="review-actions-heading" className="border-b border-border py-7"><h2 id="review-actions-heading" className="text-base font-semibold text-primary">Actions this decision would authorize</h2><div className="mt-4 divide-y divide-border border-y border-border">{snapshot.actions.map((action) => <article key={action.id} className="py-4"><div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-primary">{action.label}</p><p className="mt-1 font-mono text-[11px] text-muted">{action.id}</p></div>{action.impact ? <span className="text-sm font-semibold text-primary">{formatMoney(action.impact.amount, action.impact.currency, presentation)}</span> : null}</div><p className="mt-3 text-sm leading-6 text-secondary"><strong className="text-primary">Expected result:</strong> {action.expectedOutcome}</p></article>)}</div></section>
          <section aria-labelledby="review-facts-heading" className="border-b border-border py-7"><h2 id="review-facts-heading" className="text-base font-semibold text-primary">Facts included in this review</h2><ul className="mt-4 space-y-3">{snapshot.facts.map((fact) => <li key={fact.id} className="flex gap-3 text-sm leading-6 text-secondary"><CheckCircle2 aria-hidden="true" size={17} className="mt-1 shrink-0 text-success" /><span>{fact.statement}<span className="ml-2 text-xs text-muted">{fact.source}</span></span></li>)}</ul></section>
          <section aria-labelledby="review-evidence-heading" className="border-b border-border py-7"><h2 id="review-evidence-heading" className="text-base font-semibold text-primary">Policy guidance</h2><div className="mt-4 divide-y divide-border border-y border-border">{snapshot.evidence.map((item) => <article key={item.id} className="py-4"><div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-primary">{item.title}</p><p className="mt-1 text-xs font-medium text-info">{item.citation}</p></div><StatusLabel tone={item.conflictState === "none" ? "success" : "warning"}>{item.conflictState === "none" ? "No conflict" : "Possible conflict"}</StatusLabel></div><p className="mt-3 text-sm leading-6 text-secondary">{item.excerpt}</p></article>)}</div></section>
          <section aria-labelledby="review-risks-heading" className="py-7"><h2 id="review-risks-heading" className="text-base font-semibold text-primary">Risk checks</h2><ul className="mt-4 grid gap-3 md:grid-cols-2">{snapshot.risks.map((risk) => <li key={risk.id} className="border border-border px-4 py-4"><div className="flex items-center gap-2">{risk.outcome === "passed" ? <CheckCircle2 aria-hidden="true" size={17} className="text-success" /> : <Clock3 aria-hidden="true" size={17} className="text-warning" />}<p className="text-sm font-semibold text-primary">{risk.label}</p></div><p className="mt-2 text-xs leading-5 text-secondary">{risk.explanation}</p></li>)}</ul></section>
        </div>
        <DecisionPanel
          snapshot={snapshot}
          reserveAction={reserveAction}
          decideAction={decideAction}
        />
      </div>
    </div>
  );
}
