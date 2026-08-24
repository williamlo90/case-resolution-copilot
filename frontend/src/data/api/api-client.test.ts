import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { ApiClientError, apiRequest } from "./api-client";

const { clerkAuthMock, incomingHeadersMock, redirectMock } = vi.hoisted(() => ({
  clerkAuthMock: vi.fn(),
  incomingHeadersMock: vi.fn(),
  redirectMock: vi.fn(),
}));

vi.mock("@clerk/nextjs/server", () => ({
  auth: clerkAuthMock,
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

vi.mock("next/headers", () => ({
  headers: incomingHeadersMock,
}));

const originalAuthMode = process.env.SUPPORT_COPILOT_AUTH_MODE;
const originalPublishableKey =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const originalSecretKey = process.env.CLERK_SECRET_KEY;
const originalApiUrl = process.env.SUPPORT_COPILOT_API_INTERNAL_URL;
const originalVercelProtectionOidc =
  process.env.SUPPORT_COPILOT_VERCEL_PROTECTION_OIDC_ENABLED;

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  clerkAuthMock.mockReset();
  incomingHeadersMock.mockReset();
  redirectMock.mockReset();
  if (originalAuthMode === undefined) {
    delete process.env.SUPPORT_COPILOT_AUTH_MODE;
  } else {
    process.env.SUPPORT_COPILOT_AUTH_MODE = originalAuthMode;
  }
  if (originalPublishableKey === undefined) {
    delete process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  } else {
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY =
      originalPublishableKey;
  }
  if (originalSecretKey === undefined) {
    delete process.env.CLERK_SECRET_KEY;
  } else {
    process.env.CLERK_SECRET_KEY = originalSecretKey;
  }
  if (originalApiUrl === undefined) {
    delete process.env.SUPPORT_COPILOT_API_INTERNAL_URL;
  } else {
    process.env.SUPPORT_COPILOT_API_INTERNAL_URL = originalApiUrl;
  }
  if (originalVercelProtectionOidc === undefined) {
    delete process.env.SUPPORT_COPILOT_VERCEL_PROTECTION_OIDC_ENABLED;
  } else {
    process.env.SUPPORT_COPILOT_VERCEL_PROTECTION_OIDC_ENABLED =
      originalVercelProtectionOidc;
  }
});

describe("apiRequest", () => {
  it("uses the deterministic actor boundary and validates success responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { id: "CS-2048" } }), {
        status: 200,
        headers: { "X-Correlation-ID": "corr_success" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiRequest(
      "/api/cases/CS-2048",
      z.object({ data: z.object({ id: z.string() }) }),
    );

    expect(result.data.id).toBe("CS-2048");
    const request = fetchMock.mock.calls[0];
    expect(request[0]).toBe("http://127.0.0.1:8000/api/cases/CS-2048");
    expect(new Headers(request[1]?.headers).get("X-Actor-ID")).toBe("USR-0003");
  });

  it("uses a Clerk bearer token without development identity headers", async () => {
    process.env.SUPPORT_COPILOT_AUTH_MODE = "provider";
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "pk_placeholder";
    process.env.CLERK_SECRET_KEY = "sk_placeholder";
    clerkAuthMock.mockResolvedValue({
      getToken: vi.fn().mockResolvedValue("session-token"),
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { id: "CS-2048" } }), {
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest(
      "/api/cases/CS-2048",
      z.object({ data: z.object({ id: z.string() }) }),
    );

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("Authorization")).toBe("Bearer session-token");
    expect(headers.has("X-Actor-ID")).toBe(false);
    expect(headers.has("X-Actor-Role")).toBe(false);
  });

  it("forwards the short-lived Vercel OIDC token to a protected backend", async () => {
    process.env.SUPPORT_COPILOT_API_INTERNAL_URL =
      "https://backend-preview.vercel.app";
    process.env.SUPPORT_COPILOT_VERCEL_PROTECTION_OIDC_ENABLED = "true";
    incomingHeadersMock.mockResolvedValue(
      new Headers({ "x-vercel-oidc-token": "preview-oidc-token" }),
    );
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { id: "CS-2048" } }), {
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest(
      "/api/cases/CS-2048",
      z.object({ data: z.object({ id: z.string() }) }),
    );

    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("x-vercel-trusted-oidc-idp-token")).toBe(
      "preview-oidc-token",
    );
  });

  it("does not send a Vercel OIDC token to an untrusted backend host", async () => {
    process.env.SUPPORT_COPILOT_API_INTERNAL_URL = "https://api.example.com";
    process.env.SUPPORT_COPILOT_VERCEL_PROTECTION_OIDC_ENABLED = "true";
    incomingHeadersMock.mockResolvedValue(
      new Headers({ "x-vercel-oidc-token": "preview-oidc-token" }),
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const error = await apiRequest("/api/cases", z.unknown()).catch(
      (caught: unknown) => caught,
    );

    expect(error).toMatchObject({
      status: 503,
      code: "backend_protection_misconfigured",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fails before the backend call when the provider session is missing", async () => {
    process.env.SUPPORT_COPILOT_AUTH_MODE = "provider";
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY = "pk_placeholder";
    process.env.CLERK_SECRET_KEY = "sk_placeholder";
    clerkAuthMock.mockResolvedValue({
      getToken: vi.fn().mockResolvedValue(null),
    });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const error = await apiRequest("/api/session", z.unknown()).catch(
      (caught: unknown) => caught,
    );

    expect(error).toMatchObject({
      status: 401,
      code: "authentication_required",
    });
    expect(redirectMock).toHaveBeenCalledWith("/sign-in");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves structured errors, correlation IDs, and retry timing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "rate_limit_exceeded",
              message: "Too many requests.",
              correlation_id: "corr_rate",
              details: {},
            },
          }),
          {
            status: 429,
            headers: {
              "Retry-After": "12",
              "X-Correlation-ID": "corr_header",
            },
          },
        ),
      ),
    );

    const error = await apiRequest("/api/quality", z.unknown()).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiClientError);
    expect(error).toMatchObject({
      status: 429,
      code: "rate_limit_exceeded",
      correlationId: "corr_rate",
      retryAfterSeconds: 12,
    });
  });

  it("routes forbidden page reads to role-specific guidance", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "quality_read_forbidden",
              message: "Quality access is not allowed.",
              correlation_id: "corr_forbidden",
              details: {},
            },
          }),
          { status: 403 },
        ),
      ),
    );

    const error = await apiRequest("/api/quality", z.unknown()).catch(
      (caught: unknown) => caught,
    );

    expect(redirectMock).toHaveBeenCalledOnce();
    expect(redirectMock).toHaveBeenCalledWith("/permission-denied");
    expect(error).toMatchObject({
      status: 403,
      code: "quality_read_forbidden",
    });
  });

  it("keeps missing membership separate from a role denial", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "workspace_access_denied",
              message: "Workspace access is required.",
              correlation_id: "corr_workspace",
              details: {},
            },
          }),
          { status: 403 },
        ),
      ),
    );

    await apiRequest("/api/session", z.unknown()).catch(
      (caught: unknown) => caught,
    );

    expect(redirectMock).toHaveBeenCalledOnce();
    expect(redirectMock).toHaveBeenCalledWith("/access-denied");
  });

  it("returns command authorization errors without navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "settings_manage_forbidden",
              message: "Settings access is not allowed.",
              correlation_id: "corr_command",
              details: {},
            },
          }),
          { status: 403 },
        ),
      ),
    );

    const error = await apiRequest("/api/settings", z.unknown(), {
      method: "PATCH",
      body: {},
    }).catch((caught: unknown) => caught);

    expect(redirectMock).not.toHaveBeenCalled();
    expect(error).toMatchObject({
      status: 403,
      code: "settings_manage_forbidden",
    });
  });

  it("aborts a slow backend with a distinct timeout error", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const pending = apiRequest("/api/cases", z.unknown(), {
      timeoutMs: 25,
    }).catch((caught: unknown) => caught);
    await vi.advanceTimersByTimeAsync(25);

    await expect(pending).resolves.toMatchObject({
      status: 504,
      code: "backend_timeout",
    });
  });

  it("preserves caller cancellation separately from timeout", async () => {
    const caller = new AbortController();
    const fetchMock = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const pending = apiRequest("/api/cases", z.unknown(), {
      signal: caller.signal,
    }).catch((caught: unknown) => caught);
    caller.abort();

    await expect(pending).resolves.toMatchObject({
      status: 499,
      code: "request_cancelled",
    });
  });

  it("allows bounded caching only for reads", async () => {
    const fetchMock = vi.fn().mockImplementation(
      () => Promise.resolve(new Response(JSON.stringify({ data: {} }))),
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/settings/approval", z.unknown(), {
      cache: "force-cache",
    });
    await apiRequest("/api/settings/approval", z.unknown(), {
      method: "PUT",
      body: {},
      cache: "force-cache",
    });

    expect(fetchMock.mock.calls[0][1]?.cache).toBe("force-cache");
    expect(fetchMock.mock.calls[1][1]?.cache).toBe("no-store");
  });
});
