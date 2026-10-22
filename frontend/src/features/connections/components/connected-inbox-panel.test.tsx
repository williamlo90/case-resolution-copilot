import type {
  ConnectedInbox,
  InboxConnectionStatus,
} from "@/domain/connections/connected-inbox";
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

const connectedStatus: InboxConnectionStatus = {
  connectionId: readyInbox.id,
  accountAddress: readyInbox.accountAddress,
  importMode: "manual",
  health: "healthy",
  credentialStatus: "connected",
  syncStatus: "current",
  capabilities: ["conversation_read"],
  lastCheckedAt: readyInbox.lastCheckedAt,
  lastSuccessfulSyncAt: "2026-08-14T07:00:00.000Z",
  lastErrorCode: null,
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

  it.each([
    ["failed", "Failed"],
    ["delayed", "Delayed"],
  ] as const)("allows draft consent while preserving a %s previous update", (syncStatus, label) => {
    const { container } = render(
      <ConnectedInboxPanel
        inbox={{ ...readyInbox, canCreateDrafts: false }}
        inboxStatus={{ ...connectedStatus, syncStatus, lastErrorCode: "provider_unavailable" }}
        connectedWorkspace
        startAuthorizationAction={async (state) => state}
      />,
    );

    expect(screen.getByText("Ready", { selector: "span" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Add draft access" })).toBeEnabled();
    expect(container.querySelector<HTMLInputElement>('input[name="include_drafts"]')?.value).toBe("true");
    expect(screen.getByText("Last sync result")).toBeVisible();
    expect(screen.getByText(label, { selector: "dd" })).toBeVisible();
    expect(screen.getByText("2026-08-14 07:00 UTC")).toBeVisible();
    expect(screen.getByRole("note", { name: "Previous inbox update" })).toHaveTextContent("previous inbox update needs attention");
  });

  it("keeps draft consent unavailable without an administrator action", () => {
    render(
      <ConnectedInboxPanel
        inbox={{ ...readyInbox, canCreateDrafts: false }}
        inboxStatus={{ ...connectedStatus, syncStatus: "failed" }}
        connectedWorkspace
      />,
    );

    expect(screen.queryByRole("button", { name: "Add draft access" })).not.toBeInTheDocument();
  });

  it("keeps draft consent unavailable when authorization has expired", () => {
    render(
      <ConnectedInboxPanel
        inbox={{ ...readyInbox, canCreateDrafts: false }}
        inboxStatus={{ ...connectedStatus, credentialStatus: "expired", syncStatus: "failed" }}
        connectedWorkspace
        startAuthorizationAction={async (state) => state}
      />,
    );

    expect(screen.getByRole("button", { name: "Sign in again" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Add draft access" })).not.toBeInTheDocument();
    expect(screen.queryByRole("note", { name: "Previous inbox update" })).not.toBeInTheDocument();
  });

  it("shows no completed update when the connected inbox has never synchronized", () => {
    render(
      <ConnectedInboxPanel
        inbox={readyInbox}
        inboxStatus={{ ...connectedStatus, lastSuccessfulSyncAt: null }}
        connectedWorkspace
      />,
    );

    expect(screen.getAllByText("Not yet", { selector: "dd" })).toHaveLength(2);
    expect(screen.queryByText("Succeeded")).not.toBeInTheDocument();
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
