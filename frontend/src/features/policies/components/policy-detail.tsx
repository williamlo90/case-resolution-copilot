"use client";

import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { StatusLabel } from "@/components/ui/status-label";
import type { ServerCommand } from "@/data/commands/command-state";
import type { PolicyDetail as PolicyDetailModel } from "@/domain/policies/policy";
import { ArrowLeft, History } from "lucide-react";
import { useState } from "react";
import { PolicyLifecycleActions } from "./policy-lifecycle-actions";
import { policyStatusPresentation } from "./policy-library";

function categoryLabel(value: string): string {
  const labels: Record<string, string> = {
    all: "All case categories",
    billing_dispute: "Billing disputes",
    refund_request: "Refund requests",
    account_access: "Account access",
    service_exception: "Service exceptions",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function dimensionLabel(values: readonly string[], allLabel: string): string {
  if (values.includes("all")) return allLabel;
  return values.map((value) => value.replaceAll("_", " ")).join(", ");
}

export function PolicyDetail({
  detail,
  lifecycleAction,
}: {
  detail: PolicyDetailModel;
  lifecycleAction?: ServerCommand;
}) {
  const [selection, setSelection] = useState({
    currentVersion: detail.policy.currentVersion,
    selectedVersion: detail.policy.currentVersion,
  });
  const selectedVersion =
    selection.currentVersion === detail.policy.currentVersion
      ? selection.selectedVersion
      : detail.policy.currentVersion;

  const version =
    detail.versions.find((item) => item.version === selectedVersion) ??
    detail.versions[0];
  const currentVersion =
    detail.versions.find(
      (item) => item.version === detail.policy.currentVersion,
    ) ?? detail.versions[0];
  const state = policyStatusPresentation[detail.policy.status];
  if (!version || !currentVersion) return null;

  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <header className="border-b border-border px-4 py-4 sm:px-6 lg:px-7">
        <div className="mx-auto max-w-[1540px]">
          <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-secondary">
            <Link
              href="/policies"
              className="inline-flex items-center gap-1.5 font-medium text-info hover:underline"
            >
              <ArrowLeft aria-hidden="true" size={13} />
              Policies
            </Link>
            <span aria-hidden="true">/</span>
            <span>{detail.policy.id}</span>
          </nav>
          <div className="mt-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-semibold text-secondary">
                {detail.policy.id}
              </span>
              <StatusLabel tone={state.tone}>{state.label}</StatusLabel>
              <span className="font-mono text-xs text-muted">
                Current v{detail.policy.currentVersion}
              </span>
            </div>
            <h1 className="mt-2 text-[26px] font-semibold text-primary sm:text-[30px]">
              {detail.policy.title}
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-secondary">
              {detail.policy.description}
            </p>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1540px] lg:grid-cols-[270px_minmax(0,1fr)]">
        <aside className="border-b border-border bg-canvas/55 px-4 py-6 sm:px-6 lg:border-b-0 lg:border-r">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-primary">
            <History aria-hidden="true" size={16} />
            Version history
          </h2>
          <div className="mt-4 space-y-2">
            {detail.versions.map((item) => (
              <button
                key={item.id}
                type="button"
                  onClick={() =>
                    setSelection({
                      currentVersion: detail.policy.currentVersion,
                      selectedVersion: item.version,
                    })
                  }
                className={`w-full border px-3 py-3 text-left ${
                  selectedVersion === item.version
                    ? "border-action bg-info-bg"
                    : "border-border bg-surface hover:bg-surface-subtle"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-primary">
                    Version {item.version}
                  </span>
                  <StatusLabel tone={item.status === "published" ? "success" : "neutral"}>
                    {item.status.replaceAll("_", " ")}
                  </StatusLabel>
                </div>
                <p className="mt-2 text-[11px] text-muted">
                  {item.immutable
                    ? "Locked historical record"
                    : "Editable working version"}
                </p>
              </button>
            ))}
          </div>
        </aside>

        <div className="px-4 py-7 sm:px-6 lg:px-7">
          {lifecycleAction && detail.availableCommands.length ? (
            <PolicyLifecycleActions
              detail={detail}
              currentVersion={currentVersion}
              action={lifecycleAction}
            />
          ) : null}

          <section className="border-b border-border py-7 first:pt-0">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs uppercase text-muted">Selected version</p>
                <h2 className="mt-1 text-xl font-semibold text-primary">
                  {detail.policy.title} v{version.version}
                </h2>
              </div>
              <StatusLabel tone={version.immutable ? "success" : "warning"}>
                {version.immutable ? "Immutable record" : "Editable draft"}
              </StatusLabel>
            </div>
            <dl className="mt-5 grid gap-4 sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted">Source</dt>
                <dd className="mt-1 text-sm font-medium text-primary">
                  {detail.policy.source.name}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Owner</dt>
                <dd className="mt-1 text-sm font-medium text-primary">
                  {detail.policy.owner.name}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Used by</dt>
                <dd className="mt-1 text-sm font-medium text-primary">
                  {version.usedByCases.length} recorded cases
                </dd>
              </div>
            </dl>
          </section>

          <section aria-labelledby="coverage-heading" className="border-b border-border py-7">
            <h2 id="coverage-heading" className="text-base font-semibold text-primary">
              Coverage
            </h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <dt className="text-xs text-muted">Decision type</dt>
                <dd className="mt-1 text-sm capitalize text-primary">
                  {version.applicability.decisionScope.replaceAll("_", " ")}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Case categories</dt>
                <dd className="mt-1 text-sm text-primary">
                  {version.applicability.caseCategories.map(categoryLabel).join(", ")}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Products</dt>
                <dd className="mt-1 text-sm capitalize text-primary">
                  {dimensionLabel(version.applicability.products, "All products")}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Regions</dt>
                <dd className="mt-1 text-sm capitalize text-primary">
                  {dimensionLabel(version.applicability.regions, "All regions")}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Channels</dt>
                <dd className="mt-1 text-sm capitalize text-primary">
                  {dimensionLabel(version.applicability.channels, "All channels")}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Customer groups</dt>
                <dd className="mt-1 text-sm capitalize text-primary">
                  {dimensionLabel(
                    version.applicability.customerTiers,
                    "All customer groups",
                  )}
                </dd>
              </div>
            </dl>
          </section>

          <section aria-labelledby="clauses-heading" className="border-b border-border py-7">
            <h2 id="clauses-heading" className="text-base font-semibold text-primary">
              Policy clauses
            </h2>
            <div className="mt-4 divide-y divide-border border-y border-border">
              {version.clauses.map((clause) => (
                <article key={clause.id} className="py-5">
                  <div className="flex items-start gap-3">
                    <span className="font-mono text-[11px] text-muted">
                      {clause.id}
                    </span>
                    <div>
                      <h3 className="text-sm font-semibold text-primary">
                        {clause.heading}
                      </h3>
                      <p className="mt-2 text-sm leading-7 text-secondary">
                        {clause.text}
                      </p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section aria-labelledby="source-text-heading" className="border-b border-border py-7">
            <h2 id="source-text-heading" className="text-base font-semibold text-primary">
              Source text
            </h2>
            <blockquote className="mt-4 whitespace-pre-line border-l-2 border-info bg-canvas/55 px-4 py-4 text-sm leading-7 text-secondary">
              {version.sourceText}
            </blockquote>
          </section>

          <section aria-labelledby="historical-usage-heading" className="py-7">
            <h2 id="historical-usage-heading" className="text-base font-semibold text-primary">
              Cases that used this version
            </h2>
            {version.usedByCases.length ? (
              <div className="mt-4 divide-y divide-border border-y border-border">
                {version.usedByCases.map((usage) => (
                  <div
                    key={`${usage.caseId}-${usage.recordedAt}`}
                    className="flex items-center justify-between gap-4 py-4"
                  >
                    <div>
                      <Link
                        href={`/cases/${usage.caseId}`}
                        className="font-mono text-xs font-semibold text-info hover:underline"
                      >
                        {usage.caseId}
                      </Link>
                      <p className="mt-1 text-xs text-secondary">{usage.citation}</p>
                    </div>
                    <span className="text-xs text-muted">Evidence preserved</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-secondary">
                No case evidence references this version.
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
