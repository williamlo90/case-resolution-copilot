import type { OnboardingStep } from "@/domain/administration/administration";
import {
  ArrowRight,
  Check,
  Circle,
  Database,
  FileCheck2,
  Plug,
  ShieldCheck,
  Users,
} from "lucide-react";
import Link from "next/link";

export type OnboardingSummary = {
  organizationName: string;
  caseCount: number;
  publishedPolicyCount: number;
  activeMemberCount: number;
  connectedToolCount: number;
};

const destinations: Record<
  string,
  { href: string; action: string; icon: typeof Database }
> = {
  workspace: {
    href: "/settings/general",
    action: "Review workspace",
    icon: ShieldCheck,
  },
  team: {
    href: "/team",
    action: "Manage team",
    icon: Users,
  },
  policy: {
    href: "/policies",
    action: "Review policies",
    icon: FileCheck2,
  },
  case_source: {
    href: "/cases",
    action: "Review case source",
    icon: Database,
  },
  action_target: {
    href: "/connections",
    action: "Review action tools",
    icon: Plug,
  },
  approval_rule: {
    href: "/settings/approvals",
    action: "Review approval rules",
    icon: ShieldCheck,
  },
  test_case: {
    href: "/cases",
    action: "Run a case test",
    icon: FileCheck2,
  },
  activation: {
    href: "/cases",
    action: "Open workspace",
    icon: Check,
  },
};

function completedCount(steps: readonly OnboardingStep[]) {
  return steps.filter((step) => step.status === "complete").length;
}

export function OnboardingPage({
  steps,
  summary,
}: {
  steps: readonly OnboardingStep[];
  summary: OnboardingSummary;
}) {
  const complete = completedCount(steps);
  const ready = complete === steps.length;
  const current =
    steps.find((step) => step.status === "current") ??
    steps.find((step) => step.status === "pending") ??
    null;
  const currentDestination = current ? destinations[current.id] : null;
  const metrics = [
    { label: "Cases", value: summary.caseCount, icon: Database },
    {
      label: "Published policies",
      value: summary.publishedPolicyCount,
      icon: FileCheck2,
    },
    { label: "Active members", value: summary.activeMemberCount, icon: Users },
    {
      label: "Connected tools",
      value: summary.connectedToolCount,
      icon: Plug,
    },
  ];

  return (
    <main className="min-h-screen bg-canvas">
      <header className="border-b border-border bg-surface px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-[1100px] items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-md bg-[#17232d] text-white">
              <ShieldCheck aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-primary">
                {summary.organizationName}
              </p>
              <p className="text-xs text-muted">Workspace setup</p>
            </div>
          </div>
          <Link
            href="/cases"
            className="text-sm font-semibold text-secondary hover:text-primary"
          >
            Open workspace
          </Link>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1100px] gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[310px_minmax(0,1fr)] lg:py-12">
        <aside aria-labelledby="setup-progress-heading">
          <p
            id="setup-progress-heading"
            className="text-xs font-semibold uppercase text-muted"
          >
            Setup progress
          </p>
          <p className="mt-2 text-sm text-secondary">
            {complete} of {steps.length} complete
          </p>
          <ol className="mt-5 space-y-4">
            {steps.map((step, index) => {
              const destination = destinations[step.id];
              const StepIcon = destination?.icon ?? Circle;
              return (
                <li key={step.id} className="flex gap-3">
                  <span
                    className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${
                      step.status === "complete"
                        ? "bg-success-bg text-success"
                        : step.status === "current"
                          ? "bg-action text-white"
                          : "border border-border text-muted"
                    }`}
                  >
                    {step.status === "complete" ? (
                      <Check aria-hidden="true" size={14} />
                    ) : step.status === "current" ? (
                      <StepIcon aria-hidden="true" size={14} />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-primary">
                      {step.label}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-secondary">
                      {step.description}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </aside>

        <section
          aria-labelledby="onboarding-heading"
          className="border border-border bg-surface px-5 py-7 sm:px-8"
        >
          <p className="text-xs font-semibold uppercase text-action">
            {ready ? "Ready for pilot work" : "Workspace readiness"}
          </p>
          <h1
            id="onboarding-heading"
            className="mt-2 text-2xl font-semibold text-primary"
          >
            {ready ? "Core setup is complete" : "Finish the remaining setup"}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-secondary">
            This status comes from the current backend records. Nothing on this
            page creates sample data or changes your workspace.
          </p>

          <dl className="mt-7 grid border-l border-t border-border sm:grid-cols-2">
            {metrics.map((metric) => (
              <div
                key={metric.label}
                className="border-b border-r border-border px-4 py-4"
              >
                <dt className="flex items-center gap-2 text-xs font-medium text-secondary">
                  <metric.icon aria-hidden="true" size={15} />
                  {metric.label}
                </dt>
                <dd className="mt-2 text-2xl font-semibold text-primary">
                  {metric.value}
                </dd>
              </div>
            ))}
          </dl>

          {ready ? (
            <div
              role="status"
              className="mt-7 border border-success/25 bg-success-bg px-4 py-4"
            >
              <p className="text-sm font-semibold text-success">
                The workspace has the minimum records needed for a controlled pilot.
              </p>
              <Link
                href="/cases"
                className="mt-4 inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white"
              >
                Open case queue
                <ArrowRight aria-hidden="true" size={16} />
              </Link>
            </div>
          ) : current && currentDestination ? (
            <div
              role="status"
              className="mt-7 border border-info/25 bg-info-bg px-4 py-4"
            >
              <p className="text-xs font-semibold uppercase text-info">Next step</p>
              <p className="mt-2 text-base font-semibold text-primary">
                {current.label}
              </p>
              <p className="mt-1 text-sm leading-6 text-secondary">
                {current.description}
              </p>
              <Link
                href={currentDestination.href}
                className="mt-4 inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white"
              >
                {currentDestination.action}
                <ArrowRight aria-hidden="true" size={16} />
              </Link>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
