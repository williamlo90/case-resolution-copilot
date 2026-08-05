"use client";

import type { ActivityHistoryAction } from "@/app/(operations)/_actions/cases";
import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import type { CaseActivity, CaseWorkspace } from "@/domain/cases/case";
import { Check, ChevronUp, Clock3, Download } from "lucide-react";
import { useState, useTransition } from "react";
import { formatCaseDateTime } from "./case-workspace-format";

export function CaseActivityPanel({
  workspace,
  loadHistoryAction,
}: {
  workspace: CaseWorkspace;
  loadHistoryAction?: ActivityHistoryAction;
}) {
  const presentation = usePresentationPreferences();
  const canExport = workspace.availableCommands.includes("export_audit");
  const [activity, setActivity] = useState<CaseActivity[]>(workspace.activity);
  const [historyCursor, setHistoryCursor] = useState(
    workspace.collections.activity.nextCursor,
  );
  const [activityTotal, setActivityTotal] = useState(
    workspace.collections.activity.total,
  );
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyPending, startHistoryTransition] = useTransition();

  function loadEarlierActivity() {
    if (!loadHistoryAction || !historyCursor) return;
    startHistoryTransition(async () => {
      const result = await loadHistoryAction(historyCursor);
      if (result.status === "error") {
        setHistoryError(result.message);
        return;
      }
      setActivity((current) => {
        const currentIds = new Set(current.map((event) => event.id));
        return [
          ...result.items.filter((event) => !currentIds.has(event.id)),
          ...current,
        ];
      });
      setHistoryCursor(result.nextCursor);
      setActivityTotal(result.total);
      setHistoryError(null);
    });
  }

  return (
    <section aria-labelledby="activity-heading" className="px-4 py-6 sm:px-6 lg:px-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="activity-heading" className="text-base font-semibold text-primary">
            Case activity
          </h2>
          <p className="mt-1 text-sm text-secondary">
            Recorded events and the people or systems responsible.
          </p>
          <p className="mt-1 text-xs text-muted">
            {activity.length === activityTotal
              ? `${activityTotal} events`
              : `${activity.length} of ${activityTotal} events shown`}
          </p>
        </div>
        {canExport ? (
          <form
            action={`/cases/${encodeURIComponent(workspace.case.id)}/audit`}
            method="post"
          >
            <button
              type="submit"
              className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm font-semibold text-primary hover:bg-[#f3f6f6]"
            >
              <Download aria-hidden="true" size={16} />
              Download audit
            </button>
          </form>
        ) : null}
      </div>
      {loadHistoryAction && historyCursor ? (
        <button
          type="button"
          onClick={loadEarlierActivity}
          disabled={historyPending}
          className="mt-5 inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-primary hover:bg-surface-subtle disabled:cursor-wait disabled:opacity-60"
        >
          <ChevronUp aria-hidden="true" size={15} />
          {historyPending ? "Loading..." : "Load earlier activity"}
        </button>
      ) : null}
      {historyError ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          {historyError}
        </p>
      ) : null}
      <ol className="mt-6 divide-y divide-border border-y border-border">
        {activity.map((event) => (
          <li key={event.id} className="grid gap-3 py-4 sm:grid-cols-[24px_minmax(0,1fr)_200px]">
            <span
              className={`mt-0.5 grid size-6 place-items-center rounded-full ${
                event.status === "waiting" || event.status === "current"
                  ? "bg-warning-bg text-warning"
                  : event.status === "failed"
                    ? "bg-danger-bg text-danger"
                    : "bg-success-bg text-success"
              }`}
            >
              {event.status === "completed" ? (
                <Check aria-hidden="true" size={13} />
              ) : (
                <Clock3 aria-hidden="true" size={13} />
              )}
            </span>
            <div>
              <p className="text-sm font-semibold text-primary">{event.label}</p>
              <p className="mt-1 text-xs leading-5 text-secondary">{event.detail}</p>
              <p className="mt-1 text-[11px] text-muted">By {event.actor}</p>
            </div>
            <time dateTime={event.timestamp} className="text-xs tabular-nums text-muted sm:text-right">
              {formatCaseDateTime(event.timestamp, presentation)}
            </time>
          </li>
        ))}
      </ol>
    </section>
  );
}
