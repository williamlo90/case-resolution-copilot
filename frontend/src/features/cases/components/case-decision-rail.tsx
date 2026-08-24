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
  Clock3,
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

type HumanReviewPresentation = {
  label: string;
  description: string;
  required: boolean;
};

function humanReviewPresentation(
  workspace: CaseWorkspace,
): HumanReviewPresentation {
  if (!workspace.proposal) {
    return {
      label: "Review check pending",
      description: "Prepare the brief to check whether a reviewer is needed.",
      required: false,
    };
  }

  if (workspace.proposedActions.some((action) => action.reviewRequired)) {
    return {
      label: "Human review required before execution",
      description:
        "An authorized reviewer must approve this exact version before the proposed action can run.",
      required: true,
    };
  }

  if (workspace.proposal.state === "information_needed") {
    return {
      label: "No approval needed to request information",
      description:
        "Human review applies later, before any financial or customer-impacting action can run.",
      required: false,
    };
  }

  const laterReviewRequired = workspace.risks.some(
    (risk) => risk.outcome === "requires_review",
  );
  return laterReviewRequired
    ? {
        label: "No approval needed for this step",
        description:
          "Human review applies before a later financial or customer-impacting action can run.",
        required: false,
      }
    : {
        label: "No human review needed",
        description: "The suggested action is within the current operator's authority.",
        required: false,
      };
}

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
  const guidance =
    control.mode === "start_investigation"
      ? {
          label: "Start with the investigation",
          description:
            "Review the case evidence before preparing a decision brief.",
        }
      : control.mode === "resume_investigation"
        ? {
            label: "New information is ready",
            description:
              "Resume the investigation now so the decision can be updated.",
          }
        : {
            label: "More information is required",
            description:
              "Request the missing evidence before choosing a final action.",
          };

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium text-primary">{guidance.label}</p>
        <p className="mt-1 text-xs leading-5 text-secondary">
          {guidance.description}
        </p>
      </div>
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
  const humanReview = humanReviewPresentation(workspace);
  const canResume = workflowActions.some(
    (control) => control.mode === "resume_investigation",
  );
  const waitingForInformation =
    ["information_needed", "waiting_customer"].includes(
      workspace.case.status,
    ) && !canResume;

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
            <span
              className={`grid size-8 shrink-0 place-items-center rounded-full border ${
                humanReview.required
                  ? "border-warning/40 text-warning"
                  : "border-info/40 text-info"
              }`}
            >
              <ShieldCheck aria-hidden="true" size={17} />
            </span>
            <div>
              <p className="text-sm font-medium text-primary">
                {humanReview.label}
              </p>
              <p className="mt-1 text-xs leading-5 text-secondary">
                {humanReview.description}
              </p>
            </div>
          </div>
        </section>

        <div className="space-y-3 px-5 py-6 lg:px-7">
          {waitingForInformation ? (
            <div className="flex items-start gap-3">
              <Clock3
                aria-hidden="true"
                size={17}
                className="mt-0.5 shrink-0 text-info"
              />
              <div>
                <p className="text-sm font-medium text-primary">
                  Waiting for new information
                </p>
                <p className="mt-1 text-xs leading-5 text-secondary">
                  No action is needed until a customer reply or verified
                  evidence arrives.
                </p>
              </div>
            </div>
          ) : null}
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
                    {proposal
                      ? "Decision brief needs an update"
                      : "Decision brief is the next step"}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-secondary">
                    {proposal
                      ? "The case changed after this brief was prepared. Refresh it before choosing the next action."
                      : "Prepare it to identify verified facts, missing information, and the next safe action."}
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
          ) : null}
        </div>
      </div>
    </aside>
  );
}
