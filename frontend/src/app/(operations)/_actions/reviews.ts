"use server";

import { ApiClientError } from "@/data/api/api-client";
import type { CommandState } from "@/data/commands/command-state";
import { revalidatePath } from "next/cache";
import { commandFailure, commandSuccess, postCommand } from "./shared";

export async function reserveReview(
  reviewId: string,
  expectedVersion: number,
  _previousState: CommandState,
  _formData: FormData,
): Promise<CommandState> {
  void _previousState;
  void _formData;
  try {
    await postCommand(`/api/reviews/${encodeURIComponent(reviewId)}/reserve`, {
      expected_version: expectedVersion,
    });
    revalidatePath(`/reviews/${reviewId}`);
    revalidatePath("/reviews");
    return commandSuccess("The review is reserved to you.");
  } catch (error) {
    return commandFailure(error);
  }
}

export async function decideReview(
  reviewId: string,
  expectedVersion: number,
  snapshotFingerprint: string,
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  const decision = String(formData.get("decision") ?? "");
  const reason = String(formData.get("reason") ?? "").trim();
  if (!["approve", "request_changes", "reject", "escalate"].includes(decision)) {
    return commandFailure(
      new ApiClientError(
        "Choose an available review decision.",
        422,
        "review_decision_required",
        "unavailable",
      ),
    );
  }
  if (reason.length < 10) {
    return commandFailure(
      new ApiClientError(
        "Explain the decision in at least 10 characters.",
        422,
        "review_reason_required",
        "unavailable",
      ),
    );
  }
  try {
    await postCommand(`/api/reviews/${encodeURIComponent(reviewId)}/decisions`, {
      expected_version: expectedVersion,
      snapshot_fingerprint: snapshotFingerprint,
      decision,
      reason,
    });
    revalidatePath(`/reviews/${reviewId}`);
    revalidatePath("/reviews");
    revalidatePath("/actions");
    return commandSuccess("The review decision was recorded.");
  } catch (error) {
    return commandFailure(error);
  }
}
