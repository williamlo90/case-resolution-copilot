"use server";

import { ApiClientError } from "@/data/api/api-client";
import type { CommandState } from "@/data/commands/command-state";
import { revalidatePath } from "next/cache";
import { commandFailure, commandSuccess, postCommand } from "./shared";

export async function runActionCommand(
  actionId: string,
  expectedVersion: number,
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  const command = String(formData.get("command") ?? "");
  const endpoint = {
    execute: "execute",
    retry_safe: "retry",
    reconcile: "reconcile",
    record_manual_outcome: "manual-outcome",
    escalate: "escalate",
  }[command];
  if (!endpoint) {
    return commandFailure(
      new ApiClientError(
        "Choose an available action command.",
        422,
        "action_command_required",
        "unavailable",
      ),
    );
  }

  const body: Record<string, unknown> = { expected_version: expectedVersion };
  if (command === "record_manual_outcome") {
    const reason = String(formData.get("reason") ?? "").trim();
    const outcome = String(formData.get("outcome") ?? "");
    if (
      reason.length < 10 ||
      !["completed", "not_completed"].includes(outcome)
    ) {
      return commandFailure(
        new ApiClientError(
          "A verified outcome and a reason of at least 10 characters are required.",
          422,
          "manual_outcome_input_required",
          "unavailable",
        ),
      );
    }
    body.outcome = outcome;
    body.reason = reason;
  }
  if (command === "escalate") {
    const reason = String(formData.get("reason") ?? "").trim();
    if (reason.length < 10) {
      return commandFailure(
        new ApiClientError(
          "Explain the escalation in at least 10 characters.",
          422,
          "action_escalation_reason_required",
          "unavailable",
        ),
      );
    }
    body.reason = reason;
  }

  try {
    await postCommand(
      `/api/actions/${encodeURIComponent(actionId)}/${endpoint}`,
      body,
    );
    revalidatePath(`/actions/${actionId}`);
    revalidatePath("/actions");
    return commandSuccess("The action record was updated.");
  } catch (error) {
    return commandFailure(error);
  }
}
