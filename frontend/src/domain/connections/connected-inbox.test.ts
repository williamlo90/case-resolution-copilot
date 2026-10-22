import { describe, expect, it } from "vitest";
import {
  selectConnectedInbox,
  resolveConnectedInboxStatus,
  withoutInboxConnections,
  type InboxConnectionStatus,
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

const connectedStatus: InboxConnectionStatus = {
  connectionId: "CON-INBOX-1",
  accountAddress: "support@example.com",
  importMode: "manual",
  health: "healthy",
  credentialStatus: "connected",
  syncStatus: "current",
  capabilities: ["conversation_read"],
  lastCheckedAt: "2026-10-22T13:00:00.000Z",
  lastSuccessfulSyncAt: "2026-08-23T08:00:00.000Z",
  lastErrorCode: null,
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
        ...connectedStatus,
        syncStatus: "reauthorize",
        lastErrorCode: "credential_expired",
      }),
    ).toBe("reconnect_required");
  });

  it.each(["failed", "delayed"] as const)(
    "keeps a connected inbox ready without clearing %s synchronization history",
    (syncStatus) => {
      const status = Object.freeze({
        ...connectedStatus,
        syncStatus,
        lastErrorCode: "provider_unavailable",
      });

      expect(resolveConnectedInboxStatus("needs_attention", status)).toBe("ready");
      expect(status).toMatchObject({
        syncStatus,
        lastSuccessfulSyncAt: "2026-08-23T08:00:00.000Z",
        lastErrorCode: "provider_unavailable",
      });
    },
  );

  it.each([
    {
      label: "expired credentials",
      overrides: { credentialStatus: "expired" },
      expected: "reconnect_required",
    },
    {
      label: "missing credentials",
      overrides: { credentialStatus: "missing" },
      expected: "setup_required",
    },
    {
      label: "an unconfigured connection",
      overrides: { health: "not_configured" },
      expected: "setup_required",
    },
    {
      label: "degraded connection health",
      overrides: { health: "degraded" },
      expected: "needs_attention",
    },
    {
      label: "unavailable connection health",
      overrides: { health: "unavailable" },
      expected: "needs_attention",
    },
  ] as const)("still requires attention for $label", ({ overrides, expected }) => {
    expect(
      resolveConnectedInboxStatus("ready", {
        ...connectedStatus,
        syncStatus: "failed",
        lastErrorCode: "provider_unavailable",
        ...overrides,
      }),
    ).toBe(expected);
  });

  it("retains the known connection status when the detailed read fails", () => {
    expect(resolveConnectedInboxStatus("reconnect_required", null)).toBe(
      "reconnect_required",
    );
    expect(resolveConnectedInboxStatus("needs_attention", undefined)).toBe(
      "needs_attention",
    );
  });
});
