"use server";

import { ApiClientError, apiRequest } from "@/data/api/api-client";
import {
  apiCaseActivitySchema,
  apiConversationMessageSchema,
  mapApiCaseActivity,
  mapApiConversationMessage,
} from "@/data/cases/api-case-repository";
import type { CommandState } from "@/data/commands/command-state";
import type {
  CaseActivity,
  CaseConversationMessage,
} from "@/domain/cases/case";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import {
  commandFailure,
  commandSuccess,
  commandWarning,
  postCommand,
} from "./shared";

const decisionBriefCommandEnvelopeSchema = z.object({
  data: z.object({
    analysis: z.object({
      status: z.enum(["completed", "abstained"]),
    }),
    proposal: z.object({
      version: z.number().int().positive(),
    }),
    checkpoints: z.array(
      z.object({
        step: z.string().min(1),
        status: z.enum(["completed", "abstained"]),
      }),
    ),
  }),
});

const conversationHistoryEnvelopeSchema = z.object({
  items: z.array(apiConversationMessageSchema),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
});

const activityHistoryEnvelopeSchema = z.object({
  items: z.array(apiCaseActivitySchema),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
});

export type CaseHistoryLoadResult<Item> =
  | {
      status: "success";
      items: Item[];
      nextCursor: string | null;
      total: number;
    }
  | {
      status: "error";
      message: string;
    };

export type ConversationHistoryAction = (
  cursor: string,
) => Promise<CaseHistoryLoadResult<CaseConversationMessage>>;

export type ActivityHistoryAction = (
  cursor: string,
) => Promise<CaseHistoryLoadResult<CaseActivity>>;

export async function loadCaseConversationHistory(
  caseId: string,
  cursor: string,
): Promise<CaseHistoryLoadResult<CaseConversationMessage>> {
  const parameters = new URLSearchParams({ cursor, limit: "50" });
  try {
    const response = await apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/conversation/history?${parameters.toString()}`,
      conversationHistoryEnvelopeSchema,
    );
    return {
      status: "success",
      items: response.items.map(mapApiConversationMessage),
      nextCursor: response.next_cursor,
      total: response.total,
    };
  } catch (error) {
    return {
      status: "error",
      message: commandFailure(error).message,
    };
  }
}

export async function loadCaseActivityHistory(
  caseId: string,
  cursor: string,
): Promise<CaseHistoryLoadResult<CaseActivity>> {
  const parameters = new URLSearchParams({ cursor, limit: "100" });
  try {
    const response = await apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/activity/history?${parameters.toString()}`,
      activityHistoryEnvelopeSchema,
    );
    return {
      status: "success",
      items: response.items.map(mapApiCaseActivity),
      nextCursor: response.next_cursor,
      total: response.total,
    };
  } catch (error) {
    return {
      status: "error",
      message: commandFailure(error).message,
    };
  }
}

export async function assignCaseToMe(
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  const caseId = String(formData.get("case_id") ?? "");
  const expectedVersion = Number(formData.get("expected_version"));
  if (!caseId || !Number.isInteger(expectedVersion) || expectedVersion < 1) {
    return commandFailure(
      new ApiClientError(
        "The case assignment is no longer current. Refresh the queue.",
        422,
        "case_assignment_invalid",
        "unavailable",
      ),
    );
  }
  try {
    await postCommand(`/api/cases/${encodeURIComponent(caseId)}/assign`, {
      expected_version: expectedVersion,
    });
    revalidatePath("/cases");
    revalidatePath(`/cases/${caseId}`);
    return commandSuccess("The case was assigned to you.");
  } catch (error) {
    return commandFailure(error);
  }
}

export async function updateCaseWorkflow(
  caseId: string,
  expectedCaseVersion: number,
  targetStatus: "information_needed" | "investigating",
  _previousState: CommandState,
  _formData: FormData,
): Promise<CommandState> {
  void _previousState;
  void _formData;
  try {
    await postCommand(`/api/cases/${encodeURIComponent(caseId)}/status`, {
      expected_version: expectedCaseVersion,
      status: targetStatus,
    });
    revalidatePath(`/cases/${caseId}`);
    revalidatePath("/cases");
    return commandSuccess(
      targetStatus === "information_needed"
        ? "The case is now waiting for more information."
        : "The investigation was resumed.",
    );
  } catch (error) {
    return commandFailure(error);
  }
}

export async function submitCaseReview(
  caseId: string,
  proposalVersion: number,
  expectedCaseVersion: number,
  _previousState: CommandState,
  _formData: FormData,
): Promise<CommandState> {
  void _previousState;
  void _formData;
  try {
    await postCommand(
      `/api/cases/${encodeURIComponent(caseId)}/proposals/${proposalVersion}/reviews`,
      { expected_case_version: expectedCaseVersion },
    );
    revalidatePath(`/cases/${caseId}`);
    revalidatePath("/reviews");
    return commandSuccess("The resolution was submitted for review.");
  } catch (error) {
    return commandFailure(error);
  }
}

export async function prepareCaseDecisionBrief(
  caseId: string,
  expectedCaseVersion: number,
  currentProposalVersion: number,
  _previousState: CommandState,
  _formData: FormData,
): Promise<CommandState> {
  void _previousState;
  void _formData;
  try {
    const response = await apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/proposals`,
      decisionBriefCommandEnvelopeSchema,
      {
        method: "POST",
        body: { expected_case_version: expectedCaseVersion },
      },
    );
    revalidatePath(`/cases/${caseId}`);
    revalidatePath("/cases");

    if (response.data.proposal.version === currentProposalVersion) {
      return commandSuccess("The decision brief is already up to date.");
    }
    if (response.data.analysis.status === "abstained") {
      return commandWarning(
        "The brief needs more verified information before a resolution can be prepared.",
      );
    }
    const aiDraft = response.data.checkpoints.find(
      (checkpoint) => checkpoint.step === "ai_narrative",
    );
    if (aiDraft?.status === "completed") {
      return commandSuccess(
        "Decision brief updated. AI drafted the wording; checks and approval rules stayed unchanged.",
      );
    }
    if (aiDraft?.status === "abstained") {
      return commandWarning(
        "Decision brief updated with the built-in backup draft because AI was unavailable.",
      );
    }
    return commandSuccess(
      "Decision brief updated from the current facts and policies.",
    );
  } catch (error) {
    return commandFailure(error);
  }
}

export async function saveCaseDraft(
  caseId: string,
  expectedDraftVersion: number,
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  const subject = String(formData.get("subject") ?? "").trim();
  const body = String(formData.get("body") ?? "").trim();
  if (!subject || !body) {
    return commandFailure(
      new ApiClientError(
        "A subject and response are required.",
        422,
        "draft_input_required",
        "unavailable",
      ),
    );
  }
  try {
    await postCommand(`/api/cases/${encodeURIComponent(caseId)}/draft`, {
      expected_version: expectedDraftVersion,
      subject,
      body,
    });
    revalidatePath(`/cases/${caseId}`);
    return commandSuccess("The response draft was saved.");
  } catch (error) {
    return commandFailure(error);
  }
}

export async function addCaseConversationEntry(
  caseId: string,
  expectedCaseVersion: number,
  mode: "reply" | "note",
  channel: "email" | "chat" | "phone",
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  void _previousState;
  const body = String(formData.get("body") ?? "").trim();
  if (!body) {
    return commandFailure(
      new ApiClientError(
        mode === "note"
          ? "Write an internal note before adding it."
          : "Write a reply before adding it.",
        422,
        "conversation_body_required",
        "unavailable",
      ),
    );
  }
  try {
    await postCommand(
      mode === "note"
        ? `/api/cases/${encodeURIComponent(caseId)}/notes`
        : `/api/cases/${encodeURIComponent(caseId)}/messages`,
      mode === "note"
        ? {
            expected_case_version: expectedCaseVersion,
            body,
          }
        : {
            expected_case_version: expectedCaseVersion,
            channel,
            body,
          },
    );
    revalidatePath(`/cases/${caseId}`);
    revalidatePath("/cases");
    return commandSuccess(
      mode === "note"
        ? "The internal note was added."
        : "The reply was added to the case conversation.",
    );
  } catch (error) {
    return commandFailure(error);
  }
}
