import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { apiMoneySchema, apiRequest } from "./api-client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("validates successful transport data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ value: "accepted" }), { status: 200 }),
      ),
    );

    await expect(
      apiRequest("/api/example", z.object({ value: z.literal("accepted") })),
    ).resolves.toEqual({ value: "accepted" });
  });

  it("maps a stable error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "version_conflict",
              message: "The case changed.",
              correlation_id: "corr_contract",
              details: {},
            },
          }),
          { status: 409 },
        ),
      ),
    );

    const request = apiRequest("/api/example", z.object({ value: z.string() }));

    await expect(request).rejects.toMatchObject({
      status: 409,
      code: "version_conflict",
      correlationId: "corr_contract",
    });
  });

  it("parses exact API money into the frontend number contract", () => {
    expect(apiMoneySchema.parse({ amount: "125.50", currency: "USD" })).toEqual({
      amount: 125.5,
      currency: "USD",
    });
  });
});
