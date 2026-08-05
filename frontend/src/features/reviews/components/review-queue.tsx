"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { EmptyState } from "@/components/ui/empty-state";
import { OperationsPageHeader } from "@/components/ui/operations-page-header";
import { StatusLabel, type StatusTone } from "@/components/ui/status-label";
import type { ReviewStatus, ReviewSummary } from "@/domain/reviews/review";
import { formatMoney } from "@/features/cases/case-presentation";
import { formatDateTime } from "@/lib/presentation-format";
import { AlertTriangle, Clock3, Search, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { useMemo, useState } from "react";

const reviewStatus: Record<ReviewStatus, { label: string; tone: StatusTone }> = {
  pending: { label: "Ready for review", tone: "warning" },
  reserved: { label: "Reserved", tone: "info" },
  approved: { label: "Approved", tone: "success" },
  changes_requested: { label: "Changes requested", tone: "warning" },
  rejected: { label: "Rejected", tone: "danger" },
  escalated: { label: "Escalated", tone: "danger" },
};

function waitingLabel(minutes: number) {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`;
}

export function ReviewQueue({ reviews, sourceLabel }: { reviews: readonly ReviewSummary[]; sourceLabel: string }) {
  const presentation = usePresentationPreferences();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ReviewStatus | "all">("all");
  const [policy, setPolicy] = useState<ReviewSummary["policyState"] | "all">("all");

  const rows = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return reviews
      .filter((review) => (!normalized || [review.id, review.caseId, review.proposal.outcome, review.reviewReason, review.submittedBy.name].join(" ").toLocaleLowerCase().includes(normalized)) && (status === "all" || review.status === status) && (policy === "all" || review.policyState === policy))
      .sort((left, right) => (right.impact?.amount ?? 0) - (left.impact?.amount ?? 0) || right.waitingMinutes - left.waitingMinutes);
  }, [policy, query, reviews, status]);

  const metrics = {
    pending: reviews.filter((item) => item.status === "pending").length,
    stale: reviews.filter((item) => item.snapshotFreshness.status === "stale").length,
    conflicts: reviews.filter((item) => item.policyState === "possible_conflict").length,
  };
  const emptyState = reviews.length ? <EmptyState icon={SlidersHorizontal} title="No reviews match these filters" description="Keep the filters or reset them to return to the full review queue." action={<button type="button" onClick={() => { setQuery(""); setStatus("all"); setPolicy("all"); }} className="text-sm font-semibold text-action hover:underline">Reset filters</button>} /> : <EmptyState icon={ShieldCheck} title="No reviews yet" description="Submitted decisions that require approval will appear here." />;

  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <OperationsPageHeader title="Reviews" description="Decisions that require supervisor authority." meta={sourceLabel} />
      <section aria-label="Review summary" className="border-b border-border bg-[#f8faf9] px-4 sm:px-6 lg:px-7">
        <dl className="mx-auto grid max-w-[1540px] divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {[
            { label: "Ready for review", value: metrics.pending, icon: ShieldCheck, tone: "text-warning" },
            { label: "Outdated reviews", value: metrics.stale, icon: Clock3, tone: "text-danger" },
            { label: "Policy conflicts", value: metrics.conflicts, icon: AlertTriangle, tone: "text-warning" },
          ].map((item) => { const Icon = item.icon; return <div key={item.label} className="flex min-h-[88px] items-center gap-3 px-4 first:pl-0 sm:px-6 sm:first:pl-0"><Icon aria-hidden="true" size={20} className={item.tone} /><div><dt className="text-xs text-secondary">{item.label}</dt><dd className="mt-0.5 text-xl font-semibold tabular-nums text-primary">{item.value}</dd></div></div>; })}
        </dl>
      </section>

      <div className="mx-auto max-w-[1540px] px-4 py-6 sm:px-6 lg:px-7">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <label className="relative flex-1 lg:max-w-[620px]"><span className="sr-only">Search reviews</span><Search aria-hidden="true" size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search reviews, cases, or recommended resolutions" className="h-10 w-full rounded-md border border-border bg-surface pl-10 pr-3 text-sm outline-none focus:border-focus" /></label>
          <div className="flex flex-wrap gap-2 lg:ml-auto">
            <label><span className="sr-only">Filter review status</span><select value={status} onChange={(event) => setStatus(event.target.value as ReviewStatus | "all")} className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-primary"><option value="all">All statuses</option>{Object.entries(reviewStatus).map(([value, item]) => <option key={value} value={value}>{item.label}</option>)}</select></label>
            <label><span className="sr-only">Filter policy state</span><select value={policy} onChange={(event) => setPolicy(event.target.value as ReviewSummary["policyState"] | "all")} className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-primary"><option value="all">All policy states</option><option value="supported">Supported</option><option value="possible_conflict">Possible conflict</option><option value="missing">Missing support</option></select></label>
          </div>
        </div>

        <div className="mt-5 overflow-hidden border border-border bg-surface">
          <div className="overflow-x-auto"><table className="w-full min-w-[1250px] border-collapse text-left"><caption className="sr-only">Submitted resolution reviews</caption><thead className="bg-canvas/65 text-[11px] font-semibold uppercase text-muted"><tr className="border-b border-border"><th className="px-4 py-3">Review</th><th className="px-3 py-3">Recommended resolution</th><th className="px-3 py-3">Impact</th><th className="px-3 py-3">Why review</th><th className="px-3 py-3">Policy</th><th className="px-3 py-3">Uncertainty</th><th className="px-3 py-3">Submitted</th><th className="px-3 py-3">Waiting</th><th className="px-4 py-3">Case version</th></tr></thead>
          <tbody className="divide-y divide-border">{rows.map((review) => { const statusItem = reviewStatus[review.status]; return <tr key={review.id} className="group hover:bg-[#f2f8f7]"><td className="px-4 py-4"><Link href={`/reviews/${review.id}`} className="font-mono text-xs font-semibold text-info hover:underline">{review.id}</Link><p className="mt-1 font-mono text-[11px] text-muted">{review.caseId} / v{review.proposal.version}</p><div className="mt-2"><StatusLabel tone={statusItem.tone}>{statusItem.label}</StatusLabel></div></td><td className="max-w-[250px] px-3 py-4"><Link href={`/reviews/${review.id}`} className="block text-sm font-semibold text-primary group-hover:text-action">{review.proposal.outcome}</Link></td><td className="px-3 py-4 text-sm font-semibold text-primary">{review.impact ? formatMoney(review.impact.amount, review.impact.currency, presentation) : "No direct amount"}</td><td className="max-w-[260px] px-3 py-4 text-xs leading-5 text-secondary">{review.reviewReason}</td><td className="px-3 py-4"><StatusLabel tone={review.policyState === "supported" ? "success" : review.policyState === "missing" ? "danger" : "warning"}>{review.policyState === "supported" ? "Supported" : review.policyState === "missing" ? "Missing" : "Check conflict"}</StatusLabel></td><td className={`px-3 py-4 text-xs font-semibold capitalize ${review.uncertainty === "high" ? "text-danger" : review.uncertainty === "medium" ? "text-warning" : "text-success"}`}>{review.uncertainty}</td><td className="px-3 py-4"><p className="text-xs font-medium text-primary">{review.submittedBy.name}</p><p className="mt-1 text-[11px] text-muted">{formatDateTime(review.submittedAt, presentation, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</p></td><td className="px-3 py-4 text-xs font-semibold tabular-nums text-secondary">{waitingLabel(review.waitingMinutes)}</td><td className="px-4 py-4"><StatusLabel tone={review.snapshotFreshness.status === "current" ? "success" : "danger"}>{review.snapshotFreshness.status === "current" ? "Current" : "Outdated - blocked"}</StatusLabel>{review.reservation ? <p className="mt-2 text-[11px] text-muted">Held by {review.reservation.reviewerName}</p> : null}</td></tr>; })}</tbody></table></div>
          {!rows.length ? emptyState : <footer className="flex min-h-12 items-center border-t border-border px-4 text-xs text-muted">Showing {rows.length} of {reviews.length} reviews</footer>}
        </div>
      </div>
    </div>
  );
}
