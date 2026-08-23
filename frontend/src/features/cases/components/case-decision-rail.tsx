"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { CommandStatus } from "@/components/ui/command-status";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type { CaseWorkspace } from "@/domain/cases/case";
import { formatMoney } from "@/features/cases/case-presentation";
import type { CaseWorkflowMode } from "@/features/cases/case-workflow";
import {
  MessageCircleQuestion,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useActionState } from "react";

export type WorkflowControl = {
  mode: CaseWorkflowMode;
  action: ServerCommand;
};

function SubmitReviewControl({ action }: { action: ServerCommand }) {
  const [state, formAction, pending] = useActionState(
    action,
    initialCommandState,
  );
  return (
    <>
      <form action={formAction}>
        <button
          type="submit"
          disabled={pending}
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white hover:bg-action-strong disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send aria-hidden="true" size={16} />
          {pending ? "Submitting..." : "Submit for review"}
        </button>
      </form>
      <CommandStatus state={state} />
    </>
  );
}

function PrepareBriefControl({
  action,
  isRefresh,
}: {
  action: ServerCommand;
  isRefresh: boolean;
}) {
  const [state, formAction, pending] = useActionState(
    action,
    initialCommandState,
  );
  return (
    <div className="space-y-3">
      <form action={formAction}>
        <button
          type="submit"
          disabled={pending}
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border border-border bg-surface px-4 text-sm font-semibold text-primary hover:bg-[#f3f6f6] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw
            aria-hidden="true"
            size={16}
            className={pending ? "animate-spin" : undefined}
          />
          {pending
            ? "Preparing brief..."
            : isRefresh
              ? "Refresh brief"
              : "Prepare brief"}
        </button>
      </form>
      <CommandStatus state={state} />
    </div>
  );
}

function CaseWorkflowControl({ control }: { control: WorkflowControl }) {
  const [state, formAction, pending] = useActionState(
    control.action,
    initialCommandState,
  );
  const investigation = control.mode !== "request_information";
  const Icon = investigation ? Play : MessageCircleQuestion;
  const label =
    control.mode === "start_investigation"
      ? "Start investigation"
      : control.mode === "resume_investigation"
        ? "Resume investigation"
        : "Ask for information";
  const pendingLabel =
    control.mode === "start_investigation"
      ? "Starting..."
      : control.mode === "resume_investigation"
        ? "Resuming..."
        : "Updating...";

  return (
    <div className="space-y-3">
      <form action={formAction}>
        <button
          type="submit"
          disabled={pending}
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border border-border bg-surface px-4 text-sm font-semibold text-primary hover:bg-[#f3f6f6] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Icon aria-hidden="true" size={16} />
          {pending ? pendingLabel : label}
        </button>
      </form>
      <CommandStatus state={state} />
    </div>
  );
}

export function CaseDecisionRail({
  workspace,
  workflowActions = [],
  prepareBriefAction,
  submitReviewAction,
}: {
  workspace: CaseWorkspace;
  workflowActions?: readonly WorkflowControl[];
  prepareBriefAction?: ServerCommand;
  submitReviewAction?: ServerCommand;
}) {
  const presentation = usePresentationPreferences();
  const proposal = workspace.proposal;
  const canSubmit =
    proposal !== null &&
    workspace.availableCommands.includes("submit_for_review");

  return (
    <aside
      aria-label="Decision summary"
      className="border-t border-border bg-[#fbfcfc] xl:border-l xl:border-t-0"
    >
      <div className="xl:sticky xl:top-[60px]">
        <section className="border-b border-border px-5 py-6 lg:px-7">
          <p className="text-xs font-semibold uppercase text-muted">
            Suggested resolution
          </p>
          <h2 className="mt-3 text-lg font-semibold text-primary">
            {proposal?.outcome ?? "Resolution not prepared"}
          </h2>
          {proposal?.impact ? (
            <p className="mt-3 text-[28px] font-semibold leading-none text-success">
              {formatMoney(
                proposal.impact.amount,
                proposal.impact.currency,
                presentation,
              )}
              <span className="ml-2 text-xs font-normal text-secondary">
                estimated impact
              </span>
            </p>
          ) : (
            <p className="mt-3 text-sm text-secondary">
              No direct financial impact recorded
            </p>
          )}
        </section>

        <section className="border-b border-border px-5 py-6 lg:px-7">
          <h2 className="text-base font-semibold text-primary">
            What remains uncertain
          </h2>
          {proposal ? (
            <>
              <p className="mt-3 inline-flex items-center gap-2 text-sm font-semibold capitalize text-warning">
                <span className="size-2.5 rounded-full bg-warning" />
                {proposal.confidence} confidence
              </p>
              <p className="mt-3 text-sm leading-6 text-secondary">
                {proposal.uncertainty}
              </p>
            </>
          ) : (
            <p className="mt-3 text-sm leading-6 text-secondary">
              Investigation and policy checks must finish before a resolution
              can be reviewed.
            </p>
          )}
        </section>

        <section className="border-b border-border px-5 py-6 lg:px-7">
          <h2 className="text-base font-semibold text-primary">Human review</h2>
          <div className="mt-4 flex items-start gap-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-full border border-warning/40 text-warning">
              <ShieldCheck aria-hidden="true" size={17} />
            </span>
            <div>
              <p className="text-sm font-medium text-primary">
                Supervisor review required
              </p>
              <p className="mt-1 text-xs leading-5 text-secondary">
                The proposed action cannot run until an authorized reviewer
                approves this exact version.
              </p>
            </div>
          </div>
        </section>

        <div className="space-y-3 px-5 py-6 lg:px-7">
          {workflowActions.map((control) => (
            <CaseWorkflowControl key={control.mode} control={control} />
          ))}
          {prepareBriefAction ? (
            <>
              <div className="flex items-start gap-3 pb-1">
                <Sparkles
                  aria-hidden="true"
                  size={17}
                  className="mt-0.5 shrink-0 text-info"
                />
                <div>
                  <p className="text-sm font-medium text-primary">
                    AI-assisted wording
                  </p>
                  <p className="mt-1 text-xs leading-5 text-secondary">
                    Facts, risk checks, and approval rules stay unchanged.
                  </p>
                </div>
              </div>
              <PrepareBriefControl
                action={prepareBriefAction}
                isRefresh={proposal !== null}
              />
            </>
          ) : null}
          {canSubmit && submitReviewAction ? (
            <SubmitReviewControl action={submitReviewAction} />
          ) : (
            <button
              type="button"
              disabled
              className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white opacity-50"
            >
              <Send aria-hidden="true" size={16} />
              Submit for review
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
