"use client";

import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusLabel } from "@/components/ui/status-label";
import type {
  CaseListOptions,
  CaseListPage,
} from "@/data/cases/case-repository";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type { CaseSummary } from "@/domain/cases/case";
import {
  caseCategoryLabels,
  caseStatusPresentation,
  formatSla,
  formatUpdatedAt,
} from "@/features/cases/case-presentation";
import {
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  SlidersHorizontal,
  UserPlus,
} from "lucide-react";
import { useActionState } from "react";
import { queueHref } from "./case-queue-navigation";

function AssignCaseControl({
  item,
  action,
}: {
  item: CaseSummary;
  action?: ServerCommand;
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
  return (
    <form action={formAction}>
      <input type="hidden" name="case_id" value={item.id} />
      <input type="hidden" name="expected_version" value={item.version} />
      <button
        type="submit"
        disabled={!action || pending}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-action hover:underline disabled:cursor-not-allowed disabled:text-muted disabled:no-underline"
        title={
          action
            ? "Assign this case to me"
            : "Assignment is unavailable in sample mode"
        }
      >
        <UserPlus aria-hidden="true" size={15} />
        {pending ? "Assigning..." : "Assign to me"}
      </button>
      {state.status !== "idle" ? (
        <span
          role={state.status === "error" ? "alert" : "status"}
          className={`mt-1 block max-w-40 text-[11px] leading-4 ${
            state.status === "error" ? "text-danger" : "text-success"
          }`}
        >
          {state.message}
        </span>
      ) : null}
    </form>
  );
}

export function CaseQueueTable({
  page,
  filters,
  assignAction,
}: {
  page: CaseListPage;
  filters: CaseListOptions;
  assignAction?: ServerCommand;
}) {
  const presentation = usePresentationPreferences();
  const currentPage = Math.floor(page.offset / page.limit) + 1;
  const pageCount = Math.max(1, Math.ceil(page.total / page.limit));

  return (
    <div className="overflow-hidden border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1120px] border-collapse text-left">
          <caption className="sr-only">Open support resolution cases</caption>
          <thead className="bg-canvas/65 text-[11px] font-semibold uppercase text-muted">
            <tr className="border-b border-border">
              <th className="px-4 py-3">Case</th>
              <th className="px-3 py-3">Customer</th>
              <th className="px-3 py-3">Issue</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3">Risk</th>
              <th className="px-3 py-3">Owner</th>
              <th className="px-3 py-3">SLA</th>
              <th className="px-3 py-3">Source</th>
              <th className="px-4 py-3">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {page.items.map((item) => {
              const owner = item.owner;
              const statusItem = caseStatusPresentation[item.status];
              return (
                <tr
                  key={item.id}
                  className="group transition-colors hover:bg-[#f2f8f7]"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/cases/${item.id}`}
                      className="font-mono text-xs font-semibold text-info hover:underline"
                    >
                      {item.id}
                    </Link>
                  </td>
                  <td className="max-w-[170px] px-3 py-3">
                    <p className="truncate text-sm font-medium text-primary">
                      {item.customer.name}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-muted">
                      {item.externalReference}
                    </p>
                  </td>
                  <td className="max-w-[290px] px-3 py-3">
                    <Link
                      href={`/cases/${item.id}`}
                      className="block truncate text-sm font-medium text-primary group-hover:text-action"
                    >
                      {item.issue}
                    </Link>
                    <p className="mt-0.5 text-xs text-muted">
                      {caseCategoryLabels[item.category]}
                    </p>
                  </td>
                  <td className="px-3 py-3">
                    <StatusLabel tone={statusItem.tone}>
                      {statusItem.label}
                    </StatusLabel>
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={`inline-flex items-center gap-1.5 text-xs font-medium capitalize ${
                        item.risk === "high"
                          ? "text-danger"
                          : item.risk === "medium"
                            ? "text-warning"
                            : "text-success"
                      }`}
                    >
                      <span className="size-2 rounded-full bg-current" />
                      {item.risk}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    {owner ? (
                      <span className="flex items-center gap-2 text-xs text-primary">
                        <span className="grid size-7 place-items-center rounded-full bg-surface-subtle text-[10px] font-bold text-secondary">
                          {owner.initials}
                        </span>
                        {owner.name.split(" ")[0]}
                      </span>
                    ) : assignAction ? (
                      <AssignCaseControl item={item} action={assignAction} />
                    ) : (
                      <span className="text-xs text-muted">Unassigned</span>
                    )}
                  </td>
                  <td
                    className={`px-3 py-3 text-xs font-semibold tabular-nums ${
                      item.slaMinutesRemaining < 30
                        ? "text-danger"
                        : "text-secondary"
                    }`}
                  >
                    {formatSla(item.slaMinutesRemaining)}
                  </td>
                  <td className="px-3 py-3">
                    <span
                      className={`inline-flex items-center gap-1.5 text-xs capitalize ${
                        item.sourceFreshness.status === "stale"
                          ? "text-warning"
                          : item.sourceFreshness.status === "unavailable"
                            ? "text-danger"
                            : "text-secondary"
                      }`}
                    >
                      <span className="size-1.5 rounded-full bg-current" />
                      {item.sourceFreshness.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs tabular-nums text-muted">
                    {formatUpdatedAt(item.updatedAt, presentation)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {page.items.length ? (
        <footer className="flex min-h-12 items-center justify-between border-t border-border px-4 text-xs text-muted">
          <span>
            Showing {page.offset + 1} to {page.offset + page.items.length} of{" "}
            {page.total} cases
          </span>
          <div className="flex items-center gap-2">
            {page.previousCursor ? (
              <Link
                href={queueHref(filters, { cursor: page.previousCursor })}
                aria-label="Previous page"
                title="Previous page"
                className="grid size-8 place-items-center rounded border border-border hover:bg-surface-subtle"
              >
                <ChevronLeft aria-hidden="true" size={15} />
              </Link>
            ) : (
              <span
                aria-hidden="true"
                className="grid size-8 place-items-center rounded border border-border opacity-40"
              >
                <ChevronLeft size={15} />
              </span>
            )}
            <span className="min-w-12 text-center font-semibold text-primary">
              {currentPage} / {pageCount}
            </span>
            {page.nextCursor ? (
              <Link
                href={queueHref(filters, { cursor: page.nextCursor })}
                aria-label="Next page"
                title="Next page"
                className="grid size-8 place-items-center rounded border border-border hover:bg-surface-subtle"
              >
                <ChevronRight aria-hidden="true" size={15} />
              </Link>
            ) : (
              <span
                aria-hidden="true"
                className="grid size-8 place-items-center rounded border border-border opacity-40"
              >
                <ChevronRight size={15} />
              </span>
            )}
          </div>
        </footer>
      ) : page.summary.total ? (
        <EmptyState
          icon={SlidersHorizontal}
          title="No cases match this view"
          description="Change the search or clear the active filters."
          action={
            <Link
              href="/cases"
              className="text-sm font-semibold text-action hover:underline"
            >
              Reset view
            </Link>
          }
        />
      ) : (
        <EmptyState
          icon={CircleAlert}
          title="No cases yet"
          description="Cases will appear after a source sends one or demo data is added."
        />
      )}
    </div>
  );
}
