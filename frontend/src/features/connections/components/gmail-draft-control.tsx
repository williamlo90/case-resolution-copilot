"use client";

import { CommandStatus } from "@/components/ui/command-status";
import { StatusLabel } from "@/components/ui/status-label";
import {
  initialInboxDraftState,
  type InboxDraftAction,
  type InboxDraftState,
} from "@/features/connections/action-contracts";
import type { InboxDraftDelivery } from "@/domain/connections/connected-inbox";
import { FilePenLine, RefreshCw } from "lucide-react";
import { useActionState } from "react";

const RECONCILE_INTENT = "reconcile";

export function GmailDraftControl({
  draftVersion,
  draftStatus,
  initialDelivery = null,
  deliverDraftAction,
  reconcileDraftAction,
}: {
  draftVersion: number;
  draftStatus: "draft" | "ready" | "blocked";
  initialDelivery?: InboxDraftDelivery | null;
  deliverDraftAction?: InboxDraftAction;
  reconcileDraftAction?: InboxDraftAction;
}) {
  const [effectiveState, draftAction, pending] = useActionState(
    async (state: InboxDraftState, formData: FormData) => {
      const reconcile = formData.get("intent") === RECONCILE_INTENT;
      const action = reconcile ? reconcileDraftAction : deliverDraftAction;
      if (action) return action(state, formData);
      return {
        ...state,
        status: "error" as const,
        message: reconcile
          ? "Draft status cannot be checked right now."
          : "Connect an inbox before creating a Gmail draft.",
      };
    },
    initialDeliveryState(initialDelivery),
  );
  const delivery = effectiveState.delivery;
  const completed = delivery?.status === "completed";
  const outcomeUnknown = delivery?.status === "outcome_unknown";
  const recoveryRequired = delivery?.status === "recovery_required";
  const inProgress = delivery?.status === "ready" || delivery?.status === "running";
  const draftReady = draftStatus === "ready";
  const canCreate =
    draftReady &&
    (!delivery || delivery.status === "failed_safe");

  return (
    <section aria-labelledby="gmail-draft-heading" className="border-t border-border bg-canvas/40 px-4 py-5 sm:px-6 lg:px-7">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2">
            <FilePenLine aria-hidden="true" size={17} className="text-info" />
            <h2 id="gmail-draft-heading" className="text-sm font-semibold text-primary">
              Gmail draft
            </h2>
            {completed ? <StatusLabel tone="success">Draft ready</StatusLabel> : null}
            {outcomeUnknown ? <StatusLabel tone="warning">Check required</StatusLabel> : null}
            {recoveryRequired ? <StatusLabel tone="danger">Sign in again</StatusLabel> : null}
            {inProgress ? <StatusLabel tone="warning">In progress</StatusLabel> : null}
          </div>
          <p className="mt-2 text-xs leading-5 text-secondary">
            Create a Gmail draft from saved response version {draftVersion}.
            Review it in Gmail before taking any further action. Nothing is sent automatically.
          </p>
        </div>

        {canCreate ? (
          <form action={draftAction}>
            <button
              type="submit"
              disabled={!deliverDraftAction || pending}
              className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              <FilePenLine aria-hidden="true" size={14} />
              {pending ? "Working..." : "Create Gmail draft"}
            </button>
          </form>
        ) : null}

        {(outcomeUnknown || recoveryRequired || inProgress) && delivery ? (
          <form action={draftAction}>
            <input type="hidden" name="intent" value={RECONCILE_INTENT} />
            <input type="hidden" name="delivery_id" value={delivery.id} />
            <button
              type="submit"
              disabled={!reconcileDraftAction || pending}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-warning/40 px-3 text-xs font-semibold text-warning hover:bg-warning-bg disabled:opacity-50"
            >
              <RefreshCw aria-hidden="true" size={14} />
              {pending ? "Working..." : "Check draft status"}
            </button>
          </form>
        ) : null}
      </div>
      {!draftReady ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          {draftStatus === "blocked"
            ? "Resolve the response draft blocker before creating a Gmail draft."
            : "Finish and save the response draft before creating it in Gmail."}
        </p>
      ) : null}
      <div className="mt-3">
        <CommandStatus state={effectiveState} />
      </div>
    </section>
  );
}

function initialDeliveryState(
  delivery: InboxDraftDelivery | null,
): InboxDraftState {
  if (!delivery) return initialInboxDraftState;
  if (delivery.status === "completed") {
    return {
      ...initialInboxDraftState,
      status: "success",
      message: "Gmail draft created. Nothing was sent automatically.",
      delivery,
    };
  }
  if (
    delivery.status === "outcome_unknown" ||
    delivery.status === "ready" ||
    delivery.status === "running"
  ) {
    return {
      ...initialInboxDraftState,
      status: "success",
      tone: "warning",
      message: "The latest Gmail draft result still needs to be checked.",
      delivery,
    };
  }
  return {
    ...initialInboxDraftState,
    status: "error",
    message:
      delivery.status === "failed_safe"
        ? "No Gmail draft was created. You can try again."
        : "Sign in again, then check the latest Gmail draft result.",
    delivery,
  };
}
