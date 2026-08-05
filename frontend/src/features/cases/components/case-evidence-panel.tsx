"use client";

import { StatusLabel } from "@/components/ui/status-label";
import type { CaseWorkspace } from "@/domain/cases/case";
import { AlertCircle, CheckCircle2 } from "lucide-react";

export function CaseEvidencePanel({ workspace }: { workspace: CaseWorkspace }) {
  return (
    <div className="grid gap-8 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:px-7">
      <section aria-labelledby="policy-evidence-heading">
        <h2 id="policy-evidence-heading" className="text-base font-semibold text-primary">
          Policy guidance
        </h2>
        <p className="mt-1 text-sm text-secondary">Published guidance used for the current recommended resolution.</p>
        <div className="mt-5 divide-y divide-border border-y border-border">
          {workspace.evidence.map((item) => (
            <article key={item.id} className="py-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-primary">{item.title}</p>
                  <p className="mt-1 text-xs font-medium text-info">{item.citation}</p>
                </div>
                <StatusLabel tone={item.conflictState === "none" ? "success" : "warning"}>
                  {item.conflictState === "none" ? "No conflict" : "Check conflict"}
                </StatusLabel>
              </div>
              <blockquote className="mt-4 border-l-2 border-info pl-4 text-sm leading-6 text-secondary">
                {item.excerpt}
              </blockquote>
              <p className="mt-3 text-xs leading-5 text-secondary">
                <strong className="text-primary">Why it applies:</strong> {item.applicability}
              </p>
            </article>
          ))}
        </div>
      </section>

      <aside>
        <section aria-labelledby="risk-checks-heading">
          <h2 id="risk-checks-heading" className="text-base font-semibold text-primary">
            Risk checks
          </h2>
          <ul className="mt-5 divide-y divide-border border-y border-border">
            {workspace.risks.map((risk) => (
              <li key={risk.id} className="py-4">
                <div className="flex items-center gap-2">
                  {risk.outcome === "passed" ? (
                    <CheckCircle2 aria-hidden="true" size={17} className="text-success" />
                  ) : (
                    <AlertCircle
                      aria-hidden="true"
                      size={17}
                      className={risk.outcome === "blocked" ? "text-danger" : "text-warning"}
                    />
                  )}
                  <p className="text-sm font-semibold text-primary">{risk.label}</p>
                </div>
                <p className="mt-2 text-xs leading-5 text-secondary">{risk.explanation}</p>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="business-context-heading" className="mt-8">
          <h2 id="business-context-heading" className="text-base font-semibold text-primary">
            Business context
          </h2>
          <p className="mt-1 text-xs text-muted">
            {workspace.collections.businessContexts.returned} of{" "}
            {workspace.collections.businessContexts.total} connected records
          </p>
          {workspace.collections.businessContexts.hasMore ? (
            <p
              role="status"
              className="mt-3 border border-warning/30 bg-warning-bg px-3 py-2 text-xs leading-5 text-warning"
            >
              This case has additional connected records. Narrow or consolidate
              the relevant records before approving a final resolution.
            </p>
          ) : null}
          <div className="mt-4 divide-y divide-border border-y border-border">
            {workspace.businessContexts.map((context) => (
              <article key={context.id} className="py-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-primary">{context.label}</p>
                  <span className="text-xs capitalize text-secondary">{context.status}</span>
                </div>
                <p className="mt-1 text-xs text-muted">
                  {context.source} / {context.id}
                </p>
                <dl className="mt-3 space-y-1">
                  {Object.entries(context.fields).map(([label, value]) => (
                    <div key={label} className="flex justify-between gap-3 text-xs">
                      <dt className="capitalize text-muted">{label.replaceAll("_", " ")}</dt>
                      <dd className="text-right text-primary">{value}</dd>
                    </div>
                  ))}
                </dl>
              </article>
            ))}
          </div>
        </section>
      </aside>
    </div>
  );
}
