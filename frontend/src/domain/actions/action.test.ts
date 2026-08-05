import { actionDetailFixtures, actionSummaryFixtures, unknownOutcomeActionFixture } from "@/mocks/fixtures/action-fixtures";
import { describe, expect, it } from "vitest";
import { ActionDetailSchema, ActionSummarySchema } from "./action";

describe("action contract", () => {
  it("models execution evidence and recovery state", () => {
    expect(ActionSummarySchema.array().parse(actionSummaryFixtures)).toHaveLength(6);
    expect(ActionDetailSchema.array().parse(actionDetailFixtures)).toHaveLength(6);
  });

  it("does not permit blind retry for an unknown outcome", () => {
    expect(unknownOutcomeActionFixture.availableCommands).toContain("reconcile");
    expect(unknownOutcomeActionFixture.availableCommands).not.toContain("retry_safe");
    expect(unknownOutcomeActionFixture.availableCommands).not.toContain("execute");
  });

  it("accepts an explicitly unconfigured target without hiding the blocker", () => {
    const action = ActionDetailSchema.parse({
      ...actionDetailFixtures[0],
      action: {
        ...actionDetailFixtures[0].action,
        executionBlocker: "connection_unavailable",
      },
      targetConnection: {
        ...actionDetailFixtures[0].targetConnection,
        health: "not_configured",
      },
      executionBlocker: "connection_unavailable",
      availableCommands: [],
    });

    expect(action.targetConnection.health).toBe("not_configured");
    expect(action.action.executionBlocker).toBe("connection_unavailable");
  });
});
