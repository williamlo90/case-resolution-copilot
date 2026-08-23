import { initialInboxControlState } from "@/features/connections/action-contracts";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { requestSyncMock, revalidatePathMock } = vi.hoisted(() => ({
  requestSyncMock: vi.fn(),
  revalidatePathMock: vi.fn(),
}));

vi.mock("@/data/connections/api-connected-inbox-repository", () => ({
  apiConnectedInboxRepository: {
    requestSync: requestSyncMock,
  },
}));

vi.mock("next/cache", () => ({
  revalidatePath: revalidatePathMock,
}));

import { syncInbox } from "./inbox-controls";

async function runSync() {
  return syncInbox("CON-INBOX-1", initialInboxControlState, new FormData());
}

describe("syncInbox", () => {
  beforeEach(() => {
    requestSyncMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("reports the number of newly imported messages", async () => {
    requestSyncMock.mockResolvedValue({
      id: "ISJ-1",
      status: "completed",
      attemptCount: 1,
      importedMessages: 2,
      duplicateMessages: 0,
    });

    const result = await runSync();

    expect(result.message).toBe("Inbox updated with 2 new messages.");
    expect(revalidatePathMock).toHaveBeenCalledWith("/connections");
  });

  it("distinguishes an inbox that is already current", async () => {
    requestSyncMock.mockResolvedValue({
      id: "ISJ-2",
      status: "completed",
      attemptCount: 1,
      importedMessages: 0,
      duplicateMessages: 1,
    });

    const result = await runSync();

    expect(result.message).toBe("Inbox is up to date. No new messages found.");
  });

  it("makes a retryable failure explicit", async () => {
    requestSyncMock.mockResolvedValue({
      id: "ISJ-3",
      status: "failed",
      attemptCount: 1,
      importedMessages: 0,
      duplicateMessages: 0,
    });

    const result = await runSync();

    expect(result.message).toBe("Inbox update was delayed and can be retried.");
  });
});
