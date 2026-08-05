import type { CaseQueueSummary as QueueSummary } from "@/data/cases/case-repository";
import {
  AlertTriangle,
  CircleAlert,
  ShieldCheck,
  Users,
} from "lucide-react";

export function CaseQueueSummary({ summary }: { summary: QueueSummary }) {
  return (
    <section
      aria-label="Queue summary"
      className="border-b border-border bg-canvas/55 px-4 sm:px-6 lg:px-7"
    >
      <dl className="mx-auto grid max-w-[1540px] grid-cols-2 divide-x divide-border md:grid-cols-4">
        {[
          {
            label: "Needs attention",
            value: summary.attention,
            icon: CircleAlert,
            tone: "text-warning",
          },
          {
            label: "Waiting for review",
            value: summary.review,
            icon: ShieldCheck,
            tone: "text-warning",
          },
          {
            label: "SLA at risk",
            value: summary.slaAtRisk,
            icon: AlertTriangle,
            tone: "text-danger",
          },
          {
            label: "Unassigned",
            value: summary.unassigned,
            icon: Users,
            tone: "text-secondary",
          },
        ].map((metric) => {
          const Icon = metric.icon;
          return (
            <div
              key={metric.label}
              className="flex min-h-[88px] items-center gap-3 px-3 first:pl-0 md:px-6 md:first:pl-0"
            >
              <Icon
                aria-hidden="true"
                size={20}
                className={metric.tone}
                strokeWidth={1.8}
              />
              <div>
                <dt className="text-xs text-secondary">{metric.label}</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums text-primary">
                  {metric.value}
                </dd>
              </div>
            </div>
          );
        })}
      </dl>
    </section>
  );
}
