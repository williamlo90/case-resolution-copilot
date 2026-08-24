import { StatusLabel } from "@/components/ui/status-label";
import type { CaseWorkspace } from "@/domain/cases/case";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  MessageSquareText,
} from "lucide-react";

export function CaseDecisionBrief({ workspace }: { workspace: CaseWorkspace }) {
  return (
    <section aria-label="Decision brief" className="px-4 py-6 sm:px-6 lg:px-7 lg:py-8">
      {workspace.case.sourceFreshness.status !== "current" ? (
        <div
          role="status"
          className="mb-6 flex items-start gap-3 border border-warning/30 bg-warning-bg px-4 py-3 text-sm text-warning"
        >
          <AlertCircle aria-hidden="true" size={18} className="mt-0.5 shrink-0" />
          <p>
            <strong>
              Source data is {workspace.case.sourceFreshness.status}.
            </strong>{" "}
            Verify the connected system before approving an action.
          </p>
        </div>
      ) : null}

      <section
        aria-labelledby="issue-summary-heading"
        className="border-b border-border pb-7"
      >
        <h2
          id="issue-summary-heading"
          className="text-base font-semibold text-primary"
        >
          Issue summary
        </h2>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-secondary">
          {workspace.request.summary}
        </p>
      </section>

      <section
        aria-labelledby="verified-facts-heading"
        className="border-b border-border py-7"
      >
        <h2
          id="verified-facts-heading"
          className="text-base font-semibold text-primary"
        >
          Verified facts
        </h2>
        {workspace.facts.length ? (
          <ul className="mt-4 space-y-3">
            {workspace.facts.map((fact) => (
              <li
                key={fact.id}
                className="flex gap-3 text-sm leading-6 text-secondary"
              >
                <CheckCircle2
                  aria-hidden="true"
                  size={17}
                  className="mt-1 shrink-0 text-success"
                />
                <span>
                  {fact.statement}
                  <span className="ml-2 text-xs text-muted">{fact.source}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-secondary">
            No verified facts have been recorded yet.
          </p>
        )}
      </section>

      <section
        aria-labelledby="missing-information-heading"
        className="border-b border-border py-7"
      >
        <h2
          id="missing-information-heading"
          className="text-base font-semibold text-primary"
        >
          Information needed
        </h2>
        {workspace.missingInformation.length ? (
          <div className="mt-4 divide-y divide-border border-y border-border">
            {workspace.missingInformation.map((item) => (
              <article key={item.id} className="flex gap-3 py-4">
                <AlertCircle
                  aria-hidden="true"
                  size={17}
                  className={`mt-0.5 shrink-0 ${
                    item.blocking ? "text-danger" : "text-warning"
                  }`}
                />
                <div>
                  <p className="text-sm font-semibold text-primary">
                    {item.label}
                    {item.blocking ? (
                      <span className="ml-2 text-xs font-medium text-danger">
                        Required
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-secondary">
                    {item.description}
                  </p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-secondary">
            No missing information recorded.
          </p>
        )}
      </section>

      <section
        aria-labelledby="relevant-policies-heading"
        className="border-b border-border py-7"
      >
        <h2
          id="relevant-policies-heading"
          className="text-base font-semibold text-primary"
        >
          Relevant policies
        </h2>
        {workspace.evidence.length ? (
          <div className="mt-4 divide-y divide-border border-y border-border">
            {workspace.evidence.map((item) => (
              <article
                key={item.id}
                className="grid gap-2 py-4 sm:grid-cols-[minmax(0,1fr)_auto]"
              >
                <div>
                  <p className="text-sm font-semibold text-info">{item.title}</p>
                  <p className="mt-1 text-xs font-medium text-primary">
                    {item.citation}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-secondary">
                    {item.excerpt}
                  </p>
                </div>
                <StatusLabel
                  tone={item.freshness === "current" ? "success" : "warning"}
                >
                  {item.freshness}
                </StatusLabel>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-secondary">
            No applicable policy evidence has been recorded yet.
          </p>
        )}
      </section>

      <section aria-labelledby="rationale-heading" className="py-7">
        <h2
          id="rationale-heading"
          className="text-base font-semibold text-primary"
        >
          Why this resolution is suggested
        </h2>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-secondary">
          {workspace.proposal?.rationale ??
            "A rationale will appear after the investigation produces a policy-supported resolution."}
        </p>
      </section>

      {workspace.responseDraft?.source !== "placeholder" &&
      workspace.responseDraft ? (
        <details className="group border border-border bg-surface">
          <summary className="flex min-h-14 cursor-pointer list-none items-center gap-3 px-4 text-sm font-semibold text-primary">
            <MessageSquareText
              aria-hidden="true"
              size={18}
              className="text-secondary"
            />
            <span>Response draft</span>
            <span className="ml-auto text-xs font-medium capitalize text-success">
              {workspace.responseDraft.status}
            </span>
            <ChevronDown
              aria-hidden="true"
              size={16}
              className="text-muted transition-transform group-open:rotate-180"
            />
          </summary>
          <div className="border-t border-border px-4 py-4">
            <p className="text-xs font-semibold text-primary">
              {workspace.responseDraft.subject}
            </p>
            <p className="mt-2 whitespace-pre-line text-sm leading-6 text-secondary">
              {workspace.responseDraft.body}
            </p>
          </div>
        </details>
      ) : null}
    </section>
  );
}
