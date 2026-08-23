import { describe, expect, it } from "vitest";
import {
  selectConnectedInbox,
  resolveConnectedInboxStatus,
  withoutInboxConnections,
} from "./connected-inbox";

const genericConnection = {
  id: "CON-INBOX-1",
  name: "Inbox - support@example.com",
  providerType: "inbox",
  environment: "sandbox" as const,
  health: "healthy" as const,
  lastCheckedAt: "2026-08-14T08:00:00.000Z",
  credentialStatus: "connected" as const,
  capabilities: {
    read: ["conversation_read"],
    write: ["draft_create"],
  },
  version: 2,
};

describe("connected inbox mapping", () => {
  it("selects only the inbox capability and exposes plain domain fields", () => {
    const billing = { ...genericConnection, id: "CON-BILLING", providerType: "billing" };

    expect(selectConnectedInbox([billing, genericConnection])).toEqual({
      id: "CON-INBOX-1",
      name: "Inbox - support@example.com",
      accountAddress: "support@example.com",
      environment: "sandbox",
      status: "ready",
      lastCheckedAt: "2026-08-14T08:00:00.000Z",
      canReadConversations: true,
      canCreateDrafts: true,
      version: 2,
    });
    expect(withoutInboxConnections([billing, genericConnection])).toEqual([
      billing,
    ]);
  });

  it("maps expired credentials to an explicit recovery state", () => {
    expect(
      selectConnectedInbox([
        { ...genericConnection, credentialStatus: "expired" },
      ])?.status,
    ).toBe("reconnect_required");
  });

  it("returns null when the generic connection list has no inbox", () => {
    expect(
      selectConnectedInbox([
        { ...genericConnection, providerType: "billing" },
      ]),
    ).toBeNull();
  });

  it("lets the detailed status read model override stale generic health", () => {
    expect(
      resolveConnectedInboxStatus("ready", {
        connectionId: "CON-INBOX-1",
        accountAddress: "support@example.com",
        importMode: "manual",
        health: "healthy",
        credentialStatus: "connected",
        syncStatus: "reauthorize",
        capabilities: ["conversation_read"],
        lastCheckedAt: null,
        lastSuccessfulSyncAt: null,
        lastErrorCode: "credential_expired",
      }),
    ).toBe("reconnect_required");
  });
});
