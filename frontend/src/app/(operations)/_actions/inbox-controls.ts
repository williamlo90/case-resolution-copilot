"use server";

import { apiConnectedInboxRepository } from "@/data/connections/api-connected-inbox-repository";
import type { InboxControlState } from "@/features/connections/action-contracts";
import { revalidatePath } from "next/cache";
import { commandFailure, commandSuccess } from "./shared";

type ControlOperation = "sync" | "pause" | "resume" | "disconnect";

async function runControl(
  operation: ControlOperation,
  connectionId: string,
): Promise<InboxControlState> {
  try {
    if (operation === "sync") {
      const result = await apiConnectedInboxRepository.requestSync(connectionId);
      revalidatePath("/connections");
      const message = syncResultMessage(result);
      return {
        ...commandSuccess(message),
        connectionState: "unchanged",
      };
    }
    const result = await apiConnectedInboxRepository[operation](connectionId);
    revalidatePath("/connections");
    const message = {
      pause: "New inbox imports are paused.",
      resume: "Inbox updates resumed.",
      disconnect: result.providerRevoked
        ? "The inbox was disconnected and access was revoked."
        : "The inbox was disconnected. Provider access may still need review.",
    }[operation];
    return { ...commandSuccess(message), connectionState: result.status };
  } catch (error) {
    return { ...commandFailure(error), connectionState: "unchanged" };
  }
}

function syncResultMessage(
  result: Awaited<
    ReturnType<typeof apiConnectedInboxRepository.requestSync>
  >,
): string {
  if (result.status === "completed" && result.importedMessages > 0) {
    const suffix = result.importedMessages === 1 ? "" : "s";
    return `Inbox updated with ${result.importedMessages} new message${suffix}.`;
  }
  if (result.status === "completed") {
    return "Inbox is up to date. No new messages found.";
  }
  if (result.status === "failed") {
    return "Inbox update was delayed and can be retried.";
  }
  if (result.status === "dead") {
    return "Inbox update needs attention. Sign in again if prompted.";
  }
  return "Inbox update is still in progress.";
}

export async function syncInbox(
  connectionId: string,
  _previousState: InboxControlState,
  _formData: FormData,
): Promise<InboxControlState> {
  void _previousState;
  void _formData;
  return runControl("sync", connectionId);
}

export async function pauseInbox(
  connectionId: string,
  _previousState: InboxControlState,
  _formData: FormData,
): Promise<InboxControlState> {
  void _previousState;
  void _formData;
  return runControl("pause", connectionId);
}

export async function resumeInbox(
  connectionId: string,
  _previousState: InboxControlState,
  _formData: FormData,
): Promise<InboxControlState> {
  void _previousState;
  void _formData;
  return runControl("resume", connectionId);
}

export async function disconnectInbox(
  connectionId: string,
  _previousState: InboxControlState,
  _formData: FormData,
): Promise<InboxControlState> {
  void _previousState;
  void _formData;
  return runControl("disconnect", connectionId);
}
