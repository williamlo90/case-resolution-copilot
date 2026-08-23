import type { ConnectedInbox } from "@/domain/connections/connected-inbox";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectedInboxPanel } from "./connected-inbox-panel";

const readyInbox: ConnectedInbox = {
  id: "CON-INBOX-1",
  name: "Inbox - support@example.com",
  accountAddress: "support@example.com",
  environment: "sandbox",
  status: "ready",
  lastCheckedAt: "2026-08-14T08:00:00.000Z",
  canReadConversations: true,
  canCreateDrafts: true,
  version: 1,
};

describe("ConnectedInboxPanel", () => {
  it("states the safety boundary before an inbox is connected", () => {
    const { container } = render(
      <ConnectedInboxPanel
        inbox={null}
        connectedWorkspace
        startAuthorizationAction={async (state) => state}
      />,
    );

    expect(screen.getByText(/Reads conversations to import/)).toBeVisible();
    expect(screen.getByText(/Creates Gmail drafts for review/)).toBeVisible();
    expect(screen.getByText(/Nothing is sent automatically/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Connect Gmail" })).toBeEnabled();
    expect(
      container.querySelector<HTMLInputElement>('input[name="include_drafts"]')
        ?.value,
    ).toBe("false");
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
  });

  it("requests broader draft access only through a separate administrator action", () => {
    const { container } = render(
      <ConnectedInboxPanel
        inbox={{ ...readyInbox, canCreateDrafts: false }}
        connectedWorkspace
        startAuthorizationAction={async (state) => state}
      />,
    );

    expect(screen.getByRole("button", { name: "Add draft access" })).toBeEnabled();
    expect(
      container.querySelector<HTMLInputElement>('input[name="include_drafts"]')
        ?.value,
    ).toBe("true");
  });

  it("shows recovery instead of inbox operations for expired access", () => {
    render(
      <ConnectedInboxPanel
        inbox={{ ...readyInbox, status: "reconnect_required" }}
        connectedWorkspace
      />,
    );

    expect(screen.getByText("Sign in again", { selector: "span" })).toBeVisible();
    expect(screen.getByText(/Access is no longer current/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Load conversations" })).not.toBeInTheDocument();
  });

  it("requires an explicit action before loading conversation subjects", () => {
    render(
      <ConnectedInboxPanel inbox={readyInbox} connectedWorkspace />,
    );

    expect(screen.getByRole("button", { name: "Load conversations" })).toBeDisabled();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });

  it("uses the status endpoint read model for a paused inbox", () => {
    render(
      <ConnectedInboxPanel
        inbox={readyInbox}
        connectedWorkspace
        inboxStatus={{
          connectionId: readyInbox.id,
          accountAddress: readyInbox.accountAddress,
          importMode: "paused",
          health: "healthy",
          credentialStatus: "connected",
          syncStatus: "current",
          capabilities: ["conversation_read", "draft_create"],
          lastCheckedAt: readyInbox.lastCheckedAt,
          lastSuccessfulSyncAt: "2026-08-14T07:00:00.000Z",
          lastErrorCode: null,
        }}
      />,
    );

    expect(screen.getByText("Paused")).toBeVisible();
    expect(screen.getByText("paused", { selector: "dd" })).toBeVisible();
    expect(screen.getByText("2026-08-14 07:00 UTC")).toBeVisible();
  });
});
