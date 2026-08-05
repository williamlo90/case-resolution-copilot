import { afterEach, describe, expect, it, vi } from "vitest";
import { apiActionRepository } from "./api-action-repository";

const summary = {
  id: "AC-7001",
  case_id: "CS-2047",
  type: "issue_refund",
  label: "Issue the approved refund",
  target: "ORDER-52891",
  impact: { amount: "125.00", currency: "USD" },
  status: "ready",
  execution_blocker: "connection_unavailable",
  attempt_count: 0,
  owner: null,
  updated_at: "2026-08-04T17:04:31.000Z",
  recovery_required: false,
  version: 1,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiActionRepository", () => {
  it("preserves an action queue execution blocker", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            items: [summary],
            next_cursor: null,
            total: 1,
          }),
          { status: 200 },
        ),
      ),
    );

    const actions = await apiActionRepository.listActions();

    expect(actions[0]).toMatchObject({
      id: "AC-7001",
      executionBlocker: "connection_unavailable",
    });
  });

  it("accepts a not-configured target on action detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            data: {
              action: summary,
              approved_proposal: {
                id: "PRP-2047",
                version: 2,
                review_id: "RV-2047",
                approved_at: "2026-08-04T17:04:31.000Z",
              },
              authority: {
                actor: { id: "USR-SUP", name: "Support Supervisor" },
                role: "Support supervisor",
                rule: "Supervisor approval is required.",
              },
              typed_parameters: { order_id: "ORDER-52891" },
              target_connection: {
                id: "CN-UNCONFIGURED",
                name: "Billing operations (not configured)",
                environment: "demo",
                health: "not_configured",
                last_checked_at: null,
              },
              idempotency_key: "idem-action-2047",
              attempts: [],
              receipt: null,
              expected_outcome: "The unused order is refunded once.",
              observed_outcome: null,
              execution_blocker: "connection_unavailable",
              available_commands: [],
            },
          }),
          { status: 200 },
        ),
      ),
    );

    const detail = await apiActionRepository.getActionDetail("AC-7001");

    expect(detail?.targetConnection.health).toBe("not_configured");
    expect(detail?.executionBlocker).toBe("connection_unavailable");
    expect(detail?.action.executionBlocker).toBe("connection_unavailable");
  });
});
