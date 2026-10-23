"use server";

import { ApiClientError, apiRequest } from "@/data/api/api-client";
import {
  demoCommandSchema,
  demoEnvelopeSchema,
  scenarioSchema,
  type DemoCommand,
  type DemoScenario,
  type DemoView,
} from "@/features/v2-demo/contract";

type Result = {
  data: DemoView | null;
  error: string | null;
  code: string | null;
};
function sessionPath(id: string): string {
  if (!/^VD-[A-F0-9]{16}$/.test(id)) throw new Error("Invalid session.");
  return `/api/demo/v2/sessions/${id}`;
}
function failure(error: unknown): Pick<Result, "error" | "code"> {
  return error instanceof ApiClientError
    ? { error: error.message, code: error.code }
    : {
        error:
          "The demo could not be updated. Reload the session before continuing.",
        code: "demo_unavailable",
      };
}
export async function createV2Demo(
  scenario: DemoScenario,
  commandId: string,
): Promise<Result> {
  try {
    const selected = scenarioSchema.parse(scenario);
    if (commandId.length < 16 || commandId.length > 128)
      throw new Error("Invalid creation key.");
    const response = await apiRequest(
      "/api/demo/v2/sessions",
      demoEnvelopeSchema,
      {
        method: "POST",
        body: { scenario: selected, command_id: commandId },
        timeoutMs: 60000,
      },
    );
    return { data: response.data, error: null, code: null };
  } catch (error) {
    return { data: null, ...failure(error) };
  }
}
export async function loadV2Demo(sessionId: string): Promise<Result> {
  try {
    const response = await apiRequest(
      sessionPath(sessionId),
      demoEnvelopeSchema,
      { timeoutMs: 60000 },
    );
    return { data: response.data, error: null, code: null };
  } catch (error) {
    return { data: null, ...failure(error) };
  }
}
export async function commandV2Demo(
  sessionId: string,
  command: DemoCommand,
): Promise<Result> {
  try {
    const response = await apiRequest(
      `${sessionPath(sessionId)}/commands`,
      demoEnvelopeSchema,
      {
        method: "POST",
        body: demoCommandSchema.parse(command),
        timeoutMs: 60000,
      },
    );
    return { data: response.data, error: null, code: null };
  } catch (error) {
    // A command response may be lost after commit. Refresh persisted state, never auto-retry.
    const refreshed = await loadV2Demo(sessionId);
    return { data: refreshed.data, ...failure(error) };
  }
}
