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
    const amount =
      typeof value.amount === "number" ? value.amount : Number(value.amount);
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

function apiBaseUrl(): string {
  return (
    process.env.SUPPORT_COPILOT_API_INTERNAL_URL ?? "http://127.0.0.1:8000"
  ).replace(/\/+$/, "");
}

export function isApiNotFound(error: unknown): boolean {
  return error instanceof ApiClientError && error.status === 404;
}

export async function apiRequest<T>(
  path: string,
  schema: ZodType<T>,
  init: ApiRequestInit = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), init.timeoutMs ?? 15_000);

  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      headers: {
        Accept: "application/json",
        ...(init.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...init.headers,
      },
      cache: init.cache ?? "no-store",
      signal: controller.signal,
    });
    const payload: unknown = await response.json();

    if (!response.ok) {
      const parsed = errorEnvelopeSchema.safeParse(payload);
      if (parsed.success) {
        throw new ApiClientError(
          parsed.data.error.message,
          response.status,
          parsed.data.error.code,
          parsed.data.error.correlation_id,
          null,
        );
      }
      throw new ApiClientError(
        "The service returned an unexpected error.",
        response.status,
        "invalid_error_response",
        response.headers.get("X-Correlation-ID") ?? "corr_unknown",
      );
    }

    return schema.parse(payload);
  } finally {
    clearTimeout(timeout);
  }
}
