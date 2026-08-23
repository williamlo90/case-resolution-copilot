import { afterEach, describe, expect, it, vi } from "vitest";
import { apiReviewRepository } from "./api-review-repository";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiReviewRepository", () => {
  it("maps review business context fields into the domain model", async () => {
    const now = "2026-08-23T16:10:00.000Z";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            review: {
              id: "RV-TEST-0001",
              case_id: "CS-TEST-0001",
              proposal: {
                id: "PRP-TEST-0001",
                version: 1,
                outcome: "Reverse the verified duplicate charge",
              },
              impact: null,
              review_reason: "A supervisor decision is required.",
              policy_state: "supported",
              uncertainty: "medium",
              submitted_by: { id: "USR-0001", name: "Case Specialist" },
              submitted_at: now,
              waiting_minutes: 0,
              snapshot_freshness: {
                status: "current",
                checked_at: now,
                reason: null,
              },
              snapshot_fingerprint: "a".repeat(64),
              status: "pending",
              reservation: null,
              version: 1,
            },
            case_version: 4,
            context_fingerprint: "context-fingerprint",
            risk_rule_version: "risk:v1",
            facts: [],
            business_contexts: [
              {
                id: "CTX-PAYMENT-0001",
                type: "payment",
                label: "First settled charge",
                source: "Controlled pilot billing fixture",
                source_reference: "PAY-CRC-001-A",
                status: "settled",
                fields: { amount: "49.00", currency: "USD" },
                captured_at: now,
                source_freshness: {
                  status: "current",
                  checked_at: now,
                },
                version: 1,
              },
            ],
            evidence: [],
            risks: [],
            proposal: {
              id: "PRP-TEST-0001",
              version: 1,
              outcome: "Reverse the verified duplicate charge",
              impact: null,
              confidence: "medium",
              uncertainty: "Human approval remains pending.",
              rationale: "Two settled charges were verified.",
              state: "ready_for_review",
            },
            actions: [],
            approval_rule: {
              id: "APR-TEST-0001",
              name: "Supervisor review",
              explanation: "A supervisor must review this resolution.",
              required_role: "Supervisor",
              version: 1,
            },
            available_decisions: ["approve"],
            decision_history: [],
          },
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const snapshot = await apiReviewRepository.getReviewSnapshot("RV-TEST-0001");

    expect(snapshot?.businessContexts).toEqual([
      expect.objectContaining({
        sourceReference: "PAY-CRC-001-A",
        capturedAt: now,
        sourceFreshness: { status: "current", checkedAt: now },
        version: 1,
      }),
    ]);
  });
});
