import { auth } from "@clerk/nextjs/server";
import {
  assertProviderAuthenticationConfigured,
  providerAuthenticationEnabled,
} from "@/config/authentication";
import { redirect } from "next/navigation";
import { cache } from "react";
import { z, type ZodType } from "zod";

const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string().min(1),
    message: z.string().min(1),
    correlation_id: z.string().min(1),
    details: z.unknown().optional(),
  }),
});

export const apiMoneySchema = z
  .object({
    amount: z.union([z.number(), z.string()]),
    currency: z.string().regex(/^[A-Z]{3}$/),
  })
  .transform((value, context) => {
    const amount = typeof value.amount === "number" ? value.amount : Number(value.amount);
    if (!Number.isFinite(amount) || amount < 0) {
      context.addIssue({
        code: "custom",
        message: "Money amount must be a finite non-negative number.",
      });
      return z.NEVER;
    }
    return { amount, currency: value.currency };
  });

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly correlationId: string,
    readonly retryAfterSeconds: number | null = null,
    readonly diagnosticPaths: readonly string[] = [],
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

type ApiRequestInit = Omit<RequestInit, "body" | "headers"> & {
  body?: unknown;
  headers?: HeadersInit;
  timeoutMs?: number;
};

const READ_TIMEOUT_MS = 15_000;
const COMMAND_TIMEOUT_MS = 35_000;

function redirectReadAccessError(
  error: unknown,
  init: ApiRequestInit,
): void {
  if (!(error instanceof ApiClientError)) return;
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") return;

  if (error.status === 401) return redirect("/sign-in");
  if (error.code === "workspace_access_denied") {
    return redirect("/access-denied");
  }
  if (error.code === "workspace_selection_required") {
    return redirect("/workspace-selection");
  }
  if (error.status === 403) return redirect("/permission-denied");
}

function apiBaseUrl(): string {
  return (
    process.env.SUPPORT_COPILOT_API_INTERNAL_URL ?? "http://127.0.0.1:8000"
  ).replace(/\/+$/, "");
}

function developmentActorId(): string {
  return process.env.SUPPORT_COPILOT_DEMO_ACTOR_ID ?? "USR-0003";
}

const providerSessionToken = cache(async () => {
  const session = await auth();
  return session.getToken();
});

async function applyAuthentication(headers: Headers): Promise<void> {
  if (!providerAuthenticationEnabled()) {
    headers.set("X-Actor-ID", developmentActorId());
    return;
  }
  assertProviderAuthenticationConfigured();

  let token: string | null;
  try {
    token = await providerSessionToken();
  } catch {
    throw new ApiClientError(
      "Sign-in is temporarily unavailable.",
      503,
      "authentication_unavailable",
      "unavailable",
    );
  }
  if (!token) {
    throw new ApiClientError(
      "Sign in again to continue.",
      401,
      "authentication_required",
      "unavailable",
    );
  }
  headers.set("Authorization", `Bearer ${token}`);
  headers.delete("X-Actor-ID");
  headers.delete("X-Actor-Role");
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const retryAt = Date.parse(value);
  if (Number.isNaN(retryAt)) return null;
  return Math.max(0, Math.ceil((retryAt - Date.now()) / 1000));
}

function requestMethod(init: ApiRequestInit): string {
  return (init.method ?? "GET").toUpperCase();
}

function requestTimeout(init: ApiRequestInit): number {
  if (init.timeoutMs !== undefined) {
    if (!Number.isFinite(init.timeoutMs) || init.timeoutMs <= 0) {
      throw new TypeError("API request timeout must be a positive number.");
    }
    return init.timeoutMs;
  }
  return ["GET", "HEAD"].includes(requestMethod(init))
    ? READ_TIMEOUT_MS
    : COMMAND_TIMEOUT_MS;
}

function requestCache(init: ApiRequestInit): RequestCache {
  if (!["GET", "HEAD"].includes(requestMethod(init))) return "no-store";
  return init.cache ?? "no-store";
}

async function apiError(response: Response): Promise<ApiClientError> {
  const correlationHeader =
    response.headers.get("X-Correlation-ID") ?? "unavailable";
  let payload: z.infer<typeof errorEnvelopeSchema> | null = null;
  try {
    payload = errorEnvelopeSchema.safeParse(await response.json()).data ?? null;
  } catch {
    payload = null;
  }
  return new ApiClientError(
    payload?.error.message ?? "The backend request could not be completed.",
    response.status,
    payload?.error.code ?? "backend_request_failed",
    payload?.error.correlation_id ?? correlationHeader,
    parseRetryAfter(response.headers.get("Retry-After")),
  );
}

export async function apiRequest<T>(
  path: string,
  schema: ZodType<T>,
  init: ApiRequestInit = {},
): Promise<T> {
  const {
    body,
    headers: initHeaders,
    signal: callerSignal,
    timeoutMs: _timeoutMs,
    ...requestInit
  } = init;
  void _timeoutMs;
  const headers = new Headers(initHeaders);
  headers.set("Accept", "application/json");
  try {
    await applyAuthentication(headers);
  } catch (error) {
    redirectReadAccessError(error, init);
    throw error;
  }
  if (body !== undefined) headers.set("Content-Type", "application/json");

  const timeoutMs = requestTimeout(init);
  const controller = new AbortController();
  let timedOut = false;
  const handleCallerAbort = () => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) {
    handleCallerAbort();
  } else {
    callerSignal?.addEventListener("abort", handleCallerAbort, { once: true });
  }
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  let response: Response;
  try {
    if (callerSignal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...requestInit,
      body: body === undefined ? undefined : JSON.stringify(body),
      headers,
      signal: controller.signal,
      cache: requestCache(init),
    });
  } catch {
    if (timedOut) {
      throw new ApiClientError(
        "The backend took too long to respond.",
        504,
        "backend_timeout",
        "unavailable",
      );
    }
    if (callerSignal?.aborted) {
      throw new ApiClientError(
        "The backend request was cancelled.",
        499,
        "request_cancelled",
        "unavailable",
      );
    }
    throw new ApiClientError(
      "The backend API could not be reached.",
      503,
      "backend_unreachable",
      "unavailable",
    );
  } finally {
    clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", handleCallerAbort);
  }

  if (!response.ok) {
    const error = await apiError(response);
    redirectReadAccessError(error, init);
    throw error;
  }

  const correlationId =
    response.headers.get("X-Correlation-ID") ?? "unavailable";
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiClientError(
      "The backend returned an unreadable response.",
      502,
      "invalid_backend_response",
      correlationId,
    );
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiClientError(
      "The backend response did not match the frontend contract.",
      502,
      "invalid_backend_response",
      correlationId,
      null,
      parsed.error.issues
        .slice(0, 8)
        .map((issue) => issue.path.join(".") || "$"),
    );
  }
  return parsed.data;
}

export function isApiNotFound(error: unknown): boolean {
  return error instanceof ApiClientError && error.status === 404;
}
