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
      await apiConnectedInboxRepository.requestSync(connectionId);
      revalidatePath("/connections");
      return {
        ...commandSuccess("Inbox update requested."),
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
