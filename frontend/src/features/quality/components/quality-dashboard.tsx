"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { OperationsPageHeader } from "@/components/ui/operations-page-header";
import { StatusLabel } from "@/components/ui/status-label";
import type {
  QualityCategory,
  QualityDashboard as QualityDashboardModel,
} from "@/domain/quality/quality";
import {
  AlertTriangle,
  CheckCircle2,
  FileCheck2,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { formatDateTime } from "@/lib/presentation-format";
import { useState } from "react";

const metricIcons = {
  expected_decisions: TrendingUp,
  unsafe_actions_blocked: ShieldCheck,
  policy_evidence_present: FileCheck2,
  outcome_checks_pending: AlertTriangle,
} as const;

function metricValue(value: number, unit: string): string {
  return unit === "percent" ? `${value}%` : String(value);
}

export function QualityDashboard({
  dashboard,
}: {
  dashboard: QualityDashboardModel;
}) {
  const presentation = usePresentationPreferences();
  const [category, setCategory] = useState<QualityCategory | "all">("all");
  const rows =
    category === "all"
      ? dashboard.evidence
      : dashboard.evidence.filter((item) => item.category === category);
  const updatedAt = dashboard.sourceUpdatedAt ?? dashboard.generatedAt;

  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <OperationsPageHeader
        title="Quality"
        description="Decision quality, policy coverage, and operational outcomes."
        meta={`Updated ${formatDateTime(updatedAt, presentation, {
          dateStyle: "medium",
          timeStyle: "short",
        })}`}
      />
      <div className="mx-auto max-w-[1540px] px-4 py-6 sm:px-6 lg:px-7">
        <section
          aria-label="Quality metrics"
          className="grid gap-px border border-border bg-border sm:grid-cols-2 xl:grid-cols-4"
        >
          {dashboard.metrics.map((item) => {
            const Icon =
              metricIcons[item.key as keyof typeof metricIcons] ?? CheckCircle2;
            const healthy = item.status === "healthy";
            return (
              <div key={item.key} className="bg-surface px-5 py-5">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-secondary">{item.label}</p>
                  <Icon
                    aria-hidden="true"
                    size={18}
                    className={healthy ? "text-success" : "text-warning"}
                  />
                </div>
                <p className="mt-3 text-2xl font-semibold text-primary">
                  {metricValue(item.value, item.unit)}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {item.denominator !== null
                    ? `${item.numerator ?? 0} of ${item.denominator}`
                    : healthy
                      ? "No follow-up needed"
                      : "Follow-up required"}
                </p>
              </div>
            );
          })}
        </section>

        <section className="mt-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-primary">
                Decision evidence
              </h2>
              <p className="mt-1 text-sm text-secondary">
                Attributable checks comparing expected and observed outcomes.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <label>
                <span className="sr-only">Filter quality category</span>
                <select
                  value={category}
                  onChange={(event) =>
                    setCategory(event.target.value as QualityCategory | "all")
                  }
                  className="h-10 rounded-md border border-border bg-surface px-3 text-sm"
                >
                  <option value="all">All categories</option>
                  {dashboard.availableCategories.map((item) => (
                    <option key={item} value={item}>
                      {item.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="mt-4 overflow-x-auto border border-border">
            <table className="w-full min-w-[1080px] border-collapse text-left">
              <caption className="sr-only">
                Attributable decision quality evidence
              </caption>
              <thead className="bg-canvas/65 text-[11px] font-semibold uppercase text-muted">
                <tr className="border-b border-border">
                  <th className="px-4 py-3">Case and scenario</th>
                  <th className="px-3 py-3">Expected</th>
                  <th className="px-3 py-3">Observed</th>
                  <th className="px-3 py-3">Policy support</th>
                  <th className="px-3 py-3">Impact</th>
                  <th className="px-4 py-3">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-4">
                      <p className="text-sm font-semibold text-primary">
                        {item.scenario}
                      </p>
                      <Link
                        href={`/cases/${encodeURIComponent(item.caseId)}`}
                        className="mt-1 inline-block font-mono text-[11px] text-info hover:underline"
                      >
                        {item.caseId}
                      </Link>
                    </td>
                    <td className="px-3 py-4 text-xs text-secondary">
                      {item.expectedDecision}
                    </td>
                    <td className="px-3 py-4 text-xs text-secondary">
                      {item.observedDecision}
                    </td>
                    <td className="max-w-[260px] px-3 py-4 text-xs leading-5 text-secondary">
                      {item.policyEvidence}
                    </td>
                    <td className="max-w-[260px] px-3 py-4 text-xs leading-5 text-secondary">
                      {item.customerOrBusinessImpact ?? "No adverse impact recorded."}
                    </td>
                    <td className="px-4 py-4">
                      <StatusLabel
                        tone={item.result === "passed" ? "success" : "danger"}
                      >
                        {item.result === "passed"
                          ? "Meets expectation"
                          : "Needs attention"}
                      </StatusLabel>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length ? (
              <p className="border-t border-border px-4 py-6 text-sm text-secondary">
                No quality evidence is available for this category.
              </p>
            ) : null}
          </div>
        </section>

        <section
          aria-label="Operational quality"
          className="mt-8 grid gap-px border border-border bg-border sm:grid-cols-2 xl:grid-cols-5"
        >
          {[
            ["Open cases", dashboard.operational.openCases],
            ["Waiting for review", dashboard.operational.casesWaitingForReview],
            ["Actions completed", dashboard.operational.actionsCompleted],
            ["Failed safely", dashboard.operational.actionsFailedSafe],
            ["Outcome unknown", dashboard.operational.actionsOutcomeUnknown],
          ].map(([label, value]) => (
            <div key={label} className="bg-surface px-5 py-5">
              <p className="text-xs text-muted">{label}</p>
              <p className="mt-2 text-xl font-semibold text-primary">{value}</p>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}
