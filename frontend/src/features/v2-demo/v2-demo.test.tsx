import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  commandV2Demo,
  createV2Demo,
} from "@/app/(operations)/_actions/v2-demo";
import type { DemoView } from "./contract";
import { V2Demo } from "./v2-demo";

vi.mock("@/app/(operations)/_actions/v2-demo", () => ({
  createV2Demo: vi.fn(),
  commandV2Demo: vi.fn(),
  loadV2Demo: vi.fn(),
}));

const view: DemoView = {
  session: {
    session_id: "VD-1234567890ABCDEF",
    scenario: "timeout_recovery",
    case_id: "CS-DEMO-1",
    created_at: "2026-10-23T00:00:00Z",
  },
  case: {
    id: "CS-DEMO-1",
    version: 3,
    status: "in_progress",
    issue: "Unused course refund",
    request: "Refund the unused course.",
    records: [],
  },
  policy: {
    policy: { id: "POL-DEMO-1", version: 3, current_version: 1 },
    versions: [],
  },
  brief: null,
  review: {
    review: {
      id: "REV-DEMO-1",
      version: 3,
      status: "approved",
      snapshot_fingerprint: "a".repeat(64),
      snapshot_freshness: { status: "current", reason: null },
      submitted_by: { name: "Simulated specialist" },
    },
    evidence: [],
    decision_history: [],
  },
  action: {
    action: {
      id: "ACT-DEMO-1",
      version: 4,
      status: "outcome_unknown",
      attempt_count: 1,
    },
    idempotency_key: "operation-1234567890",
    typed_parameters: { amount_minor: "24000" },
    execution_blocker: "duplicate",
    observed_outcome: "Unknown",
    receipt: null,
  },
  target: {
    objects: { "COURSE-1": { owner: "CUSTOMER-1", credited_minor: "24000" } },
    effect_count: 1,
    operations: [
      {
        operation_id: "operation-1234567890",
        target: "COURSE-1",
        changes: { credited_minor: "24000" },
      },
    ],
    storage: "database_event_ledger",
  },
  lifecycle: { version: 3, status: "in_progress", events: [] },
  observations: [],
};

describe("V2 interactive operator controls", () => {
  beforeEach(() => vi.clearAllMocks());

  it("requires an explicit operator action to create a session and reuses a lost-response key", async () => {
    vi.mocked(createV2Demo).mockResolvedValue({
      data: null,
      error: "Response lost",
      code: "unavailable",
    });
    render(<V2Demo sessions={[]} />);
    expect(createV2Demo).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Create fresh session" }),
    );
    await screen.findByText("Response lost (unavailable)");
    fireEvent.click(
      screen.getByRole("button", { name: "Retry session creation" }),
    );
    await waitFor(() => expect(createV2Demo).toHaveBeenCalledTimes(2));
    expect(vi.mocked(createV2Demo).mock.calls[0][1]).toBe(
      vi.mocked(createV2Demo).mock.calls[1][1],
    );
  });

  it("sends the displayed operation, snapshot and version without automatically retrying a denied command", async () => {
    vi.mocked(createV2Demo).mockResolvedValue({
      data: view,
      error: null,
      code: null,
    });
    vi.mocked(commandV2Demo).mockResolvedValue({
      data: view,
      error: "Duplicate dispatch blocked",
      code: "action_execution_blocked",
    });
    render(<V2Demo sessions={[]} />);
    fireEvent.click(
      screen.getByRole("button", { name: "Create fresh session" }),
    );
    await screen.findByRole("heading", {
      name: "Independent synthetic target",
    });
    fireEvent.change(screen.getByLabelText("Simulated role"), {
      target: { value: "reviewer" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "5. Execute / try again" }),
    );
    await screen.findByText(
      "Duplicate dispatch blocked (action_execution_blocked)",
    );
    expect(commandV2Demo).toHaveBeenCalledTimes(1);
    expect(commandV2Demo).toHaveBeenCalledWith(
      view.session.session_id,
      expect.objectContaining({
        role: "reviewer",
        command: "execute",
        expected_version: 4,
        resource_id: "ACT-DEMO-1",
        snapshot_fingerprint: "a".repeat(64),
      }),
    );
    expect(screen.getByText("1 effect(s) · 0 verified event(s)")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "7. Close with proof" }),
    ).toBeDisabled();
  });
});
