import { initialInboxImportState } from "@/features/connections/action-contracts";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { importThreadMock, revalidatePathMock } = vi.hoisted(() => ({
  importThreadMock: vi.fn(),
  revalidatePathMock: vi.fn(),
}));

vi.mock("@/data/connections/api-connected-inbox-repository", () => ({
  apiConnectedInboxRepository: {
    importThread: importThreadMock,
  },
}));

vi.mock("next/cache", () => ({
  revalidatePath: revalidatePathMock,
}));

import { importInboxThread } from "./inbox-import";

function importForm(): FormData {
  const form = new FormData();
  form.set("provider_thread_id", "thread-1");
  form.set("category", "billing_dispute");
  form.set("urgency", "high");
  form.set("risk", "medium");
  form.set("due_at", "2026-08-25T10:00:00.000Z");
  return form;
}

describe("importInboxThread", () => {
  beforeEach(() => {
    importThreadMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("describes a replay as an unchanged existing case", async () => {
    importThreadMock.mockResolvedValue({
      caseId: "CS-EMAIL-1",
      importedMessages: 0,
      duplicateMessages: 1,
    });

    const result = await importInboxThread(
      "CON-INBOX-1",
      initialInboxImportState,
      importForm(),
    );

    expect(result).toMatchObject({
      status: "success",
      caseId: "CS-EMAIL-1",
      message: "No new messages. Existing case CS-EMAIL-1 is unchanged.",
    });
  });

  it("distinguishes new messages added to an existing case", async () => {
    importThreadMock.mockResolvedValue({
      caseId: "CS-EMAIL-1",
      importedMessages: 1,
      duplicateMessages: 2,
    });

    const result = await importInboxThread(
      "CON-INBOX-1",
      initialInboxImportState,
      importForm(),
    );

    expect(result.message).toBe("1 new message added to case CS-EMAIL-1.");
  });
});
