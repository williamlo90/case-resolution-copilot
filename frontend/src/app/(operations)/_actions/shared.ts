import { ApiClientError, apiRequest } from "@/data/api/api-client";
import type { CommandState } from "@/data/commands/command-state";
import { z } from "zod";

export const commandEnvelopeSchema = z.object({ data: z.unknown() });

export function commandFailure(error: unknown): CommandState {
  if (error instanceof ApiClientError) {
    return {
      status: "error",
      message: error.message,
      correlationId:
        error.correlationId === "unavailable" ? null : error.correlationId,
      retryAfterSeconds: error.retryAfterSeconds,
    };
  }
  return {
    status: "error",
    message: "The command could not be completed.",
    correlationId: null,
    retryAfterSeconds: null,
  };
}

export function commandSuccess(message: string): CommandState {
  return {
    status: "success",
    message,
    correlationId: null,
    retryAfterSeconds: null,
  };
}

export function commandWarning(message: string): CommandState {
  return {
    status: "success",
    message,
    correlationId: null,
    retryAfterSeconds: null,
    tone: "warning",
  };
}

export async function postCommand(path: string, body: unknown): Promise<void> {
  await apiRequest(path, commandEnvelopeSchema, {
    method: "POST",
    body,
  });
}
