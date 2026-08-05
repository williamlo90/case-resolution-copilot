"use client";

import { CommandStatus } from "@/components/ui/command-status";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type { PolicyDetail, PolicyVersion } from "@/domain/policies/policy";
import {
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  FilePenLine,
  Send,
  Trash2,
} from "lucide-react";
import { useActionState } from "react";

const categoryOptions = [
  { value: "all", label: "All case categories" },
  { value: "billing_dispute", label: "Billing disputes" },
  { value: "refund_request", label: "Refund requests" },
  { value: "account_access", label: "Account access" },
  { value: "service_exception", label: "Service exceptions" },
] as const;

function dateValue(value: string | null): string {
  return value?.slice(0, 10) ?? "";
}

function DraftFields({ version }: { version: PolicyVersion }) {
  return (
    <div className="grid gap-4">
      <label className="grid gap-2 text-sm font-medium text-primary">
        Policy text
        <textarea
          name="source_text"
          required
          minLength={20}
          rows={10}
          defaultValue={version.sourceText}
          className="resize-y rounded-md border border-border px-3 py-3 font-mono text-sm leading-6 outline-none focus:border-focus"
        />
      </label>
      <label className="grid gap-2 text-sm font-medium text-primary">
        Decision type
        <input
          name="decision_scope"
          required
          defaultValue={version.applicability.decisionScope}
          className="h-11 rounded-md border border-border px-3 text-sm outline-none focus:border-focus"
        />
      </label>
      <fieldset>
        <legend className="text-sm font-medium text-primary">Case categories</legend>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {categoryOptions.map((category) => (
            <label
              key={category.value}
              className="flex min-h-10 items-center gap-3 border border-border px-3 text-sm text-primary"
            >
              <input
                type="checkbox"
                name="case_categories"
                value={category.value}
                defaultChecked={version.applicability.caseCategories.includes(
                  category.value,
                )}
                className="size-4 accent-[#0f817c]"
              />
              {category.label}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-2 text-sm font-medium text-primary">
          Effective from
          <input
            type="date"
            name="effective_from"
            defaultValue={dateValue(version.effectiveFrom)}
            className="h-11 rounded-md border border-border px-3 text-sm"
          />
        </label>
        <label className="grid gap-2 text-sm font-medium text-primary">
          Effective until
          <input
            type="date"
            name="effective_to"
            defaultValue={dateValue(version.effectiveTo)}
            className="h-11 rounded-md border border-border px-3 text-sm"
          />
        </label>
      </div>
    </div>
  );
}

export function PolicyLifecycleActions({
  detail,
  currentVersion,
  action,
}: {
  detail: PolicyDetail;
  currentVersion: PolicyVersion;
  action: ServerCommand;
}) {
  const [state, formAction, pending] = useActionState(
    action,
    initialCommandState,
  );
  const commands = new Set(detail.availableCommands);
  const draftCommand = commands.has("retry_source")
    ? "retry_source"
    : commands.has("create_draft")
      ? "create_draft"
      : null;

  return (
    <section
      aria-labelledby="policy-actions-heading"
      className="border-b border-border pb-7"
    >
      <h2 id="policy-actions-heading" className="text-base font-semibold text-primary">
        Policy actions
      </h2>

      {draftCommand ? (
        <details className="group mt-4 border-y border-border">
          <summary className="flex min-h-14 cursor-pointer list-none items-center gap-3 text-sm font-semibold text-primary">
            <FilePenLine aria-hidden="true" size={17} className="text-info" />
            {draftCommand === "retry_source"
              ? "Repair policy source"
              : "Create editable version"}
            <ChevronDown
              aria-hidden="true"
              size={16}
              className="ml-auto text-muted transition-transform group-open:rotate-180"
            />
          </summary>
          <form action={formAction} className="border-t border-border py-5">
            <DraftFields version={currentVersion} />
            <button
              type="submit"
              name="command"
              value={draftCommand}
              disabled={pending}
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong disabled:opacity-50"
            >
              <FilePenLine aria-hidden="true" size={16} />
              {pending
                ? "Saving..."
                : draftCommand === "retry_source"
                  ? "Check source again"
                  : "Create draft version"}
            </button>
          </form>
        </details>
      ) : null}

      {commands.has("submit_review") ? (
        <form action={formAction} className="mt-4">
          <button
            type="submit"
            name="command"
            value="submit_review"
            disabled={pending}
            className="inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong disabled:opacity-50"
          >
            <Send aria-hidden="true" size={16} />
            {pending ? "Submitting..." : "Submit for policy review"}
          </button>
        </form>
      ) : null}

      {commands.has("publish") || commands.has("schedule") ? (
        <form action={formAction} className="mt-4 border-y border-border py-5">
          <label className="grid max-w-sm gap-2 text-sm font-medium text-primary">
            Effective date
            <input
              type="date"
              name="effective_from"
              className="h-11 rounded-md border border-border px-3 text-sm"
            />
          </label>
          <div className="mt-4 flex flex-wrap gap-2">
            {commands.has("publish") ? (
              <button
                type="submit"
                name="command"
                value="publish"
                disabled={pending}
                className="inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong disabled:opacity-50"
              >
                <CheckCircle2 aria-hidden="true" size={16} />
                {pending ? "Publishing..." : "Publish now"}
              </button>
            ) : null}
            {commands.has("schedule") ? (
              <button
                type="submit"
                name="command"
                value="schedule"
                disabled={pending}
                className="inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm font-semibold text-primary hover:bg-surface-subtle disabled:opacity-50"
              >
                <CalendarClock aria-hidden="true" size={16} />
                Schedule
              </button>
            ) : null}
          </div>
        </form>
      ) : null}

      {commands.has("retire") ? (
        <details className="group mt-4 border-y border-border">
          <summary className="flex min-h-12 cursor-pointer list-none items-center gap-2 text-sm font-semibold text-danger">
            <Trash2 aria-hidden="true" size={16} />
            Retire this policy
            <ChevronDown
              aria-hidden="true"
              size={16}
              className="ml-auto text-muted transition-transform group-open:rotate-180"
            />
          </summary>
          <form action={formAction} className="border-t border-border py-4">
            <p className="text-sm leading-6 text-secondary">
              Historical case evidence remains available, but this version will stop guiding new cases.
            </p>
            <button
              type="submit"
              name="command"
              value="retire"
              disabled={pending}
              className="mt-4 inline-flex h-10 items-center gap-2 rounded-md border border-danger/35 px-4 text-sm font-semibold text-danger hover:bg-danger-bg disabled:opacity-50"
            >
              <Trash2 aria-hidden="true" size={16} />
              {pending ? "Retiring..." : "Confirm retirement"}
            </button>
          </form>
        </details>
      ) : null}

      <div className="mt-4">
        <CommandStatus state={state} />
      </div>
    </section>
  );
}
