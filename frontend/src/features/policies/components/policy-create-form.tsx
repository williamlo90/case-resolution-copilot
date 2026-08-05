"use client";

import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { CommandStatus } from "@/components/ui/command-status";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import { ArrowLeft, FilePlus2, ShieldCheck } from "lucide-react";
import { useActionState } from "react";

const categories = [
  { value: "billing_dispute", label: "Billing disputes" },
  { value: "refund_request", label: "Refund requests" },
  { value: "account_access", label: "Account access" },
  { value: "service_exception", label: "Service exceptions" },
] as const;

export function PolicyCreateForm({ action }: { action: ServerCommand }) {
  const [state, formAction, pending] = useActionState(
    action,
    initialCommandState,
  );

  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <header className="border-b border-border px-4 py-4 sm:px-6 lg:px-7">
        <div className="mx-auto max-w-[1240px]">
          <Link
            href="/policies"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-info hover:underline"
          >
            <ArrowLeft aria-hidden="true" size={13} />
            Policies
          </Link>
          <h1 className="mt-4 text-[26px] font-semibold text-primary sm:text-[30px]">
            New policy
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-secondary">
            Add source guidance and define which support cases it covers.
          </p>
        </div>
      </header>

      <form
        action={formAction}
        className="mx-auto grid max-w-[1240px] lg:grid-cols-[minmax(0,1fr)_340px]"
      >
        <div className="px-4 py-7 sm:px-6 lg:px-7">
          <section className="border-b border-border pb-7">
            <h2 className="text-base font-semibold text-primary">Policy details</h2>
            <div className="mt-5 grid gap-5">
              <label className="grid gap-2 text-sm font-medium text-primary">
                Title
                <input
                  name="title"
                  required
                  maxLength={300}
                  className="h-11 rounded-md border border-border px-3 text-sm outline-none focus:border-focus"
                />
              </label>
              <label className="grid gap-2 text-sm font-medium text-primary">
                Summary
                <textarea
                  name="description"
                  required
                  maxLength={1000}
                  rows={3}
                  className="resize-y rounded-md border border-border px-3 py-2.5 text-sm leading-6 outline-none focus:border-focus"
                />
              </label>
              <label className="grid gap-2 text-sm font-medium text-primary">
                Source name
                <input
                  name="source_name"
                  required
                  maxLength={500}
                  placeholder="Customer support handbook"
                  className="h-11 rounded-md border border-border px-3 text-sm outline-none focus:border-focus"
                />
              </label>
            </div>
          </section>

          <section className="border-b border-border py-7">
            <h2 id="policy-source-text-heading" className="text-base font-semibold text-primary">
              Policy text
            </h2>
            <textarea
              name="source_text"
              aria-labelledby="policy-source-text-heading"
              required
              minLength={20}
              rows={14}
              placeholder={"## Eligibility\nDescribe the rule and the evidence required.\n\n## Authority\nDescribe when human review is required."}
              className="mt-4 w-full resize-y rounded-md border border-border px-3 py-3 font-mono text-sm leading-6 outline-none focus:border-focus"
            />
          </section>

          <section className="py-7">
            <h2 className="text-base font-semibold text-primary">Applies to</h2>
            <div className="mt-5 grid gap-5 sm:grid-cols-2">
              <label className="grid gap-2 text-sm font-medium text-primary sm:col-span-2">
                Decision type
                <select
                  name="decision_scope"
                  defaultValue="general_support"
                  className="h-11 rounded-md border border-border bg-surface px-3 text-sm"
                >
                  <option value="general_support">General support resolution</option>
                  <option value="billing_adjustment">Billing adjustment</option>
                  <option value="account_recovery">Account recovery</option>
                  <option value="service_exception">Service exception</option>
                  <option value="privacy_handling">Customer data handling</option>
                </select>
              </label>
              <fieldset className="sm:col-span-2">
                <legend className="text-sm font-medium text-primary">
                  Case categories
                </legend>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {categories.map((category, index) => (
                    <label
                      key={category.value}
                      className="flex min-h-11 items-center gap-3 border border-border px-3 text-sm text-primary"
                    >
                      <input
                        type="checkbox"
                        name="case_categories"
                        value={category.value}
                        defaultChecked={index === 0}
                        className="size-4 accent-[#0f817c]"
                      />
                      {category.label}
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="grid gap-2 text-sm font-medium text-primary">
                Effective from
                <input
                  type="date"
                  name="effective_from"
                  className="h-11 rounded-md border border-border px-3 text-sm"
                />
              </label>
              <label className="grid gap-2 text-sm font-medium text-primary">
                Effective until
                <input
                  type="date"
                  name="effective_to"
                  className="h-11 rounded-md border border-border px-3 text-sm"
                />
              </label>
            </div>
          </section>
        </div>

        <aside className="border-t border-border bg-[#fbfcfc] px-5 py-6 lg:border-l lg:border-t-0 lg:px-7">
          <div className="lg:sticky lg:top-[84px]">
            <div className="flex items-start gap-3">
              <ShieldCheck
                aria-hidden="true"
                size={18}
                className="mt-0.5 shrink-0 text-info"
              />
              <div>
                <h2 className="text-sm font-semibold text-primary">
                  Starts as a draft
                </h2>
                <p className="mt-1 text-xs leading-5 text-secondary">
                  A separate review and publish step is required before this policy can guide a case.
                </p>
              </div>
            </div>
            <button
              type="submit"
              disabled={pending}
              className="mt-6 inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong disabled:cursor-not-allowed disabled:opacity-50"
            >
              <FilePlus2 aria-hidden="true" size={17} />
              {pending ? "Creating draft..." : "Create policy draft"}
            </button>
            <div className="mt-3">
              <CommandStatus state={state} />
            </div>
          </div>
        </aside>
      </form>
    </div>
  );
}
