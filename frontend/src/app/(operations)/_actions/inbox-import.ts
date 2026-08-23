"use server";

import { ApiClientError } from "@/data/api/api-client";
import { apiConnectedInboxRepository } from "@/data/connections/api-connected-inbox-repository";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import type {
  InboxImportState,
  InboxThreadsState,
} from "@/features/connections/action-contracts";
import { commandFailure, commandSuccess } from "./shared";

const importInputSchema = z.object({
  providerThreadId: z.string().min(1),
  category: z.enum([
    "billing_dispute",
    "refund_request",
    "account_access",
    "service_exception",
  ]),
  urgency: z.enum(["low", "medium", "high", "critical"]),
  risk: z.enum(["low", "medium", "high"]),
  dueAt: z.string().min(1),
});

export async function listInboxThreads(
  connectionId: string,
  previousState: InboxThreadsState,
  formData: FormData,
): Promise<InboxThreadsState> {
  const cursor = String(formData.get("cursor") ?? "") || null;
  try {
    const page = await apiConnectedInboxRepository.listThreads(
      connectionId,
      cursor,
    );
    return {
      ...commandSuccess(
        page.items.length
          ? "Recent conversations loaded."
          : "No recent conversations were found.",
      ),
      items: page.items,
      nextCursor: page.nextCursor,
    };
  } catch (error) {
    return {
      ...commandFailure(error),
      items: previousState.items,
      nextCursor: previousState.nextCursor,
    };
  }
}

export async function importInboxThread(
  connectionId: string,
  _previousState: InboxImportState,
  formData: FormData,
): Promise<InboxImportState> {
  void _previousState;
  const parsed = importInputSchema.safeParse({
    providerThreadId: formData.get("provider_thread_id"),
    category: formData.get("category"),
    urgency: formData.get("urgency"),
    risk: formData.get("risk"),
    dueAt: formData.get("due_at"),
  });
  const dueAt = parsed.success ? new Date(parsed.data.dueAt) : null;
  if (!parsed.success || !dueAt || Number.isNaN(dueAt.getTime())) {
    return {
      ...commandFailure(
        new ApiClientError(
          "Choose a conversation, case details, and a valid due date.",
          422,
          "inbox_import_input_invalid",
          "unavailable",
        ),
      ),
      caseId: null,
    };
  }

  try {
    const result = await apiConnectedInboxRepository.importThread(
      connectionId,
      { ...parsed.data, dueAt: dueAt.toISOString() },
    );
    revalidatePath("/connections");
    revalidatePath("/cases");
    return {
      ...commandSuccess(
        `Case ${result.caseId} created from ${result.importedMessages} messages.`,
      ),
      caseId: result.caseId,
    };
  } catch (error) {
    return { ...commandFailure(error), caseId: null };
  }
}
