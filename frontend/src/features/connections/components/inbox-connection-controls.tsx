"use client";

import { CommandStatus } from "@/components/ui/command-status";
import { StatusLabel } from "@/components/ui/status-label";
import {
  initialInboxControlState,
  type InboxControlAction,
  type InboxControlState,
} from "@/features/connections/action-contracts";
import { Pause, Play, RefreshCw, Unplug } from "lucide-react";
import { useActionState } from "react";

type ControlOperation = "sync" | "pause" | "resume" | "disconnect";

function unavailableControl(
  previousState: InboxControlState,
): Promise<InboxControlState> {
  return Promise.resolve({
    ...previousState,
    status: "error",
    message: "You do not have permission to manage this inbox.",
  });
}

export function InboxConnectionControls({
  syncAction,
  pauseAction,
  resumeAction,
  disconnectAction,
  initiallyPaused = false,
}: {
  syncAction?: InboxControlAction;
  pauseAction?: InboxControlAction;
  resumeAction?: InboxControlAction;
  disconnectAction?: InboxControlAction;
  initiallyPaused?: boolean;
}) {
  const actions: Record<ControlOperation, InboxControlAction | undefined> = {
    sync: syncAction,
    pause: pauseAction,
    resume: resumeAction,
    disconnect: disconnectAction,
  };
  const initialState: InboxControlState = initiallyPaused
    ? { ...initialInboxControlState, connectionState: "paused" }
    : initialInboxControlState;
  const [state, formAction, pending] = useActionState(
    async (previousState: InboxControlState, formData: FormData) => {
      const operation = String(formData.get("operation")) as ControlOperation;
      return (actions[operation] ?? unavailableControl)(previousState, formData);
    },
    initialState,
  );
  const paused = state.connectionState === "paused";
  const disconnected = state.connectionState === "disconnected";
  const canManage = Object.values(actions).some(Boolean);

  return (
    <section aria-labelledby="inbox-controls-heading" className="border-t border-border pt-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 id="inbox-controls-heading" className="text-sm font-semibold text-primary">
            Inbox updates
          </h3>
          <p className="mt-1 text-xs text-muted">
            Update on demand or pause new inbox imports.
          </p>
        </div>
        {disconnected ? (
          <StatusLabel tone="neutral">Disconnected</StatusLabel>
        ) : paused ? (
          <StatusLabel tone="warning">Paused</StatusLabel>
        ) : (
          <StatusLabel tone="success">Active</StatusLabel>
        )}
      </div>

      {canManage ? (
        <form action={formAction} className="mt-4 flex flex-wrap gap-2">
          <button
            type="submit"
            name="operation"
            value="sync"
            disabled={pending || disconnected}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-primary hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw aria-hidden="true" size={14} />
            Update now
          </button>
          {paused ? (
            <button
              type="submit"
              name="operation"
              value="resume"
              disabled={pending || disconnected}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-primary hover:bg-surface-subtle disabled:opacity-50"
            >
              <Play aria-hidden="true" size={14} /> Resume updates
            </button>
          ) : (
            <button
              type="submit"
              name="operation"
              value="pause"
              disabled={pending || disconnected}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold text-primary hover:bg-surface-subtle disabled:opacity-50"
            >
              <Pause aria-hidden="true" size={14} /> Pause updates
            </button>
          )}
          <button
            type="submit"
            name="operation"
            value="disconnect"
            disabled={pending || disconnected}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-danger/35 px-3 text-xs font-semibold text-danger hover:bg-danger-bg disabled:opacity-50"
          >
            <Unplug aria-hidden="true" size={14} /> Disconnect
          </button>
        </form>
      ) : (
        <p className="mt-4 text-xs text-secondary">
          Only a workspace administrator can change this connection.
        </p>
      )}
      {pending ? (
        <p role="status" className="mt-3 text-xs text-muted">
          Updating inbox settings...
        </p>
      ) : null}
      <div className="mt-3">
        <CommandStatus state={state} />
      </div>
    </section>
  );
}
