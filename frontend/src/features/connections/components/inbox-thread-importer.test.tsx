import { fireEvent, render, screen } from "@testing-library/react";
import { initialInboxThreadsState } from "@/features/connections/action-contracts";
import { describe, expect, it } from "vitest";
import { InboxThreadImporter } from "./inbox-thread-importer";

describe("InboxThreadImporter", () => {
  it("keeps long conversation subjects inside narrow layouts", async () => {
    const subject =
      "[CRC-PILOT-001] Duplicate charge after plan upgrade with a deliberately long subject";
    render(
      <InboxThreadImporter
        listThreadsAction={async () => ({
          ...initialInboxThreadsState,
          status: "success",
          tone: "success",
          message: "Recent conversations loaded.",
          correlationId: null,
          items: [
            {
              providerThreadId: "thread-1",
              subject,
              latestMessageAt: "2026-08-23T13:29:00.000Z",
            },
          ],
          nextCursor: null,
        })}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Load conversations" }));

    const subjectLabel = await screen.findByTitle(subject);
    expect(subjectLabel).toHaveClass("truncate");
    expect(subjectLabel.parentElement).toHaveClass(
      "min-w-0",
      "flex-1",
      "overflow-hidden",
    );
    expect(subjectLabel.closest("fieldset")).toHaveClass("min-w-0");
  });
});
