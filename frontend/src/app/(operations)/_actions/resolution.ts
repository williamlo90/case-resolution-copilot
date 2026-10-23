"use server";

import { apiRequest } from "@/data/api/api-client";
import type { CommandState } from "@/data/commands/command-state";
import { resolutionKindSchema } from "@/features/resolution/contract";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import { commandFailure, commandSuccess } from "./shared";

export async function updateCaseResolution(caseId: string, version: number, _state: CommandState, form: FormData): Promise<CommandState> {
  const parsed = z.object({
    kind: resolutionKindSchema, reason: z.string().trim().min(3).max(1000),
    reference: z.string().trim().min(1).max(200), command_id: z.string().uuid(),
  }).safeParse(Object.fromEntries(form));
  if (!parsed.success) return { status: "error", message: "Add a reason and the required reference before continuing.", correlationId: null, retryAfterSeconds: null };
  try {
    await apiRequest(`/api/cases/${encodeURIComponent(caseId)}/resolution`, z.object({ event_id: z.string(), kind: z.string() }), {
      method: "POST", body: { ...parsed.data, expected_version: version },
    });
    revalidatePath(`/cases/${caseId}`);
    revalidatePath("/cases");
    return commandSuccess("The case resolution record was updated.");
  } catch (error) {
    revalidatePath(`/cases/${caseId}`);
    return commandFailure(error);
  }
}
