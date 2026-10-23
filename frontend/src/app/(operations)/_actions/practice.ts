"use server";
import { revalidatePath } from "next/cache";
import type { CommandState } from "@/data/commands/command-state";
import { demoCommandSchema, type DemoCommand } from "@/features/v2-demo/contract";
import { commandV2Demo } from "./v2-demo";
import { commandSuccess, commandFailure } from "./shared";

export type PracticeBinding = Omit<DemoCommand, "command_id" | "reason" | "reference">;
export async function runPracticeStep(sessionId: string, binding: PracticeBinding, _state: CommandState, form: FormData): Promise<CommandState> {
  const kind = String(form.get("kind") ?? "");
  let command = binding.command;
  let reference = String(form.get("reference") ?? "").trim() || null;
  if (binding.command === "close") {
    if (!["completed", "reopened"].includes(kind)) return commandFailure(new Error("Unsupported resolution."));
    command = kind === "completed" ? "close" : "reopen";
  }
  if (binding.command === "execute") {
    const requested = String(form.get("command") ?? "");
    if (requested !== "execute" && requested !== "reconcile") return commandFailure(new Error("Unsupported action."));
    command = requested;
  }
  const reason = String(form.get("reason") ?? "").trim();
  if (["approve", "close", "reopen"].includes(command) && reason.length < 3) return commandFailure(new Error("A reason is required."));
  if (!["close", "reopen"].includes(command)) reference = null;
  const parsed = demoCommandSchema.safeParse({
    ...binding, command,
    decision: binding.command === "approve" ? String(form.get("decision") ?? "approve") : undefined,
    command_id: String(form.get("command_id") ?? crypto.randomUUID()),
    reason: reason || "Operator requested the next workflow step.",
    reference,
  });
  if (!parsed.success) return commandFailure(new Error("Invalid step details."));
  const result = await commandV2Demo(sessionId, parsed.data);
  for (const path of ["/cases", "/reviews", "/actions", "/policies"]) revalidatePath(path);
  revalidatePath("/cases/[caseId]", "page");
  revalidatePath("/reviews/[reviewId]", "page");
  revalidatePath("/actions/[actionId]", "page");
  revalidatePath("/policies/[policyId]", "page");
  if (result.error) return {status:"error", message:result.error, correlationId:null, retryAfterSeconds:null};
  return commandSuccess(command === "execute" ? "Request recorded. Check the target outcome before closing the case." : command === "reconcile" ? "Outcome check recorded. Review the result below." : "Saved. The current result and next step are shown above.");
}
