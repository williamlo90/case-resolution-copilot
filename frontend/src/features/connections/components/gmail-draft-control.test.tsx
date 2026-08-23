import type { InboxDraftAction } from "@/features/connections/action-contracts";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GmailDraftControl } from "./gmail-draft-control";

const completedAction: InboxDraftAction = async () => ({
  status: "success",
  message: "Gmail draft created. Nothing was sent automatically.",
  correlationId: null,
  retryAfterSeconds: null,
  delivery: {
    id: "DDL-1",
    status: "completed",
    attemptCount: 1,
    providerDraftId: "gmail-draft-1",
    lastErrorCode: null,
  },
});

describe("GmailDraftControl", () => {
  it("restores an unresolved delivery after refresh and offers reconciliation", () => {
    render(
      <GmailDraftControl
        draftVersion={3}
        draftStatus="ready"
        initialDelivery={{
          id: "DDL-PERSISTED",
          status: "outcome_unknown",
          attemptCount: 1,
          providerDraftId: null,
          lastErrorCode: "provider_timeout",
        }}
        deliverDraftAction={completedAction}
        reconcileDraftAction={completedAction}
      />,
    );

    expect(screen.getByRole("button", { name: "Check draft status" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Create Gmail draft" })).not.toBeInTheDocument();
  });

  it("creates a draft from the bound version without presenting a send command", async () => {
    render(
      <GmailDraftControl
        draftVersion={7}
        draftStatus="ready"
        deliverDraftAction={completedAction}
      />,
    );

    expect(screen.getByText(/saved response version 7/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create Gmail draft" }));
    await waitFor(() => expect(screen.getByText("Draft ready")).toBeVisible());
    expect(screen.getByRole("status")).toHaveTextContent(
      "Nothing was sent automatically",
    );
  });

  it("offers reconciliation instead of a second create attempt when the outcome is unknown", async () => {
    const unknownAction: InboxDraftAction = async () => ({
      status: "success",
      tone: "warning",
      message: "We could not confirm whether Gmail created the draft.",
      correlationId: null,
      retryAfterSeconds: null,
      delivery: {
        id: "DDL-2",
        status: "outcome_unknown",
        attemptCount: 1,
        providerDraftId: null,
        lastErrorCode: "provider_timeout",
      },
    });
    render(
      <GmailDraftControl
        draftVersion={3}
        draftStatus="ready"
        deliverDraftAction={unknownAction}
        reconcileDraftAction={completedAction}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Create Gmail draft" }));
    expect(await screen.findByRole("button", { name: "Check draft status" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Create Gmail draft" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check draft status" }));
    await waitFor(() => expect(screen.getByText("Draft ready")).toBeVisible());
  });

  it("keeps an unresolved result when reconciliation fails", async () => {
    const failedReconciliation: InboxDraftAction = async (state) => ({
      ...state,
      status: "error",
      message: "Gmail could not be checked right now.",
    });
    render(
      <GmailDraftControl
        draftVersion={3}
        draftStatus="ready"
        initialDelivery={{
          id: "DDL-UNRESOLVED",
          status: "outcome_unknown",
          attemptCount: 1,
          providerDraftId: null,
          lastErrorCode: "provider_timeout",
        }}
        deliverDraftAction={completedAction}
        reconcileDraftAction={failedReconciliation}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Check draft status" }));
    expect(await screen.findByText("Gmail could not be checked right now.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Check draft status" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Create Gmail draft" })).not.toBeInTheDocument();
  });
});
