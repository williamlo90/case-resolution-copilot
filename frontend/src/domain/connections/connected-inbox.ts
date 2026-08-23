import { z } from "zod";

export const InboxThreadSchema = z.object({
  providerThreadId: z.string().min(1),
  subject: z.string().min(1),
  latestMessageAt: z.string().datetime(),
});

export const InboxImportResultSchema = z.object({
  caseId: z.string().min(1),
  conversationId: z.string().min(1),
  importedMessages: z.number().int().nonnegative(),
  duplicateMessages: z.number().int().nonnegative(),
  latestMessageAt: z.string().datetime(),
});

export const InboxSyncJobSchema = z.object({
  id: z.string().min(1),
  status: z.enum(["pending", "running", "completed", "failed", "dead"]),
  attemptCount: z.number().int().nonnegative(),
});

export const InboxAuthorizationResultSchema = z.object({
  connectionId: z.string().min(1),
  accountAddress: z.string().min(1),
  returnPath: z.string().min(1),
  capabilities: z.array(
    z.enum(["conversation_read", "draft_create"]),
  ),
});

export const InboxDraftDeliverySchema = z.object({
  id: z.string().min(1),
  status: z.enum([
    "ready",
    "running",
    "completed",
    "failed_safe",
    "outcome_unknown",
    "recovery_required",
  ]),
  attemptCount: z.number().int().nonnegative(),
  providerDraftId: z.string().min(1).nullable(),
  lastErrorCode: z.string().min(1).nullable(),
});

export const ConnectedInboxSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  accountAddress: z.string().min(1),
  environment: z.enum(["demo", "sandbox", "production"]),
  status: z.enum([
    "ready",
    "needs_attention",
    "reconnect_required",
    "setup_required",
  ]),
  lastCheckedAt: z.string().datetime().nullable(),
  canReadConversations: z.boolean(),
  canCreateDrafts: z.boolean(),
  version: z.number().int().positive(),
});

export const InboxConnectionStatusSchema = z.object({
  connectionId: z.string().min(1),
  accountAddress: z.string().min(1),
  importMode: z.enum(["paused", "manual", "scheduled"]),
  health: z.enum(["healthy", "degraded", "unavailable", "not_configured"]),
  credentialStatus: z.enum(["demo", "connected", "missing", "expired"]),
  syncStatus: z.enum(["current", "syncing", "delayed", "failed", "reauthorize"]),
  capabilities: z.array(z.string().min(1)),
  lastCheckedAt: z.string().datetime().nullable(),
  lastSuccessfulSyncAt: z.string().datetime().nullable(),
  lastErrorCode: z.string().min(1).nullable(),
});

type GenericConnectionRecord = {
  id: string;
  name: string;
  providerType: string;
  environment: "demo" | "sandbox" | "production";
  health: "healthy" | "degraded" | "unavailable" | "not_configured";
  lastCheckedAt: string | null;
  credentialStatus: "demo" | "connected" | "missing" | "expired";
  capabilities: { read: readonly string[]; write: readonly string[] };
  version: number;
};

function connectionStatus(
  connection: GenericConnectionRecord,
): z.infer<typeof ConnectedInboxSchema>["status"] {
  if (connection.credentialStatus === "expired") return "reconnect_required";
  if (
    connection.credentialStatus === "missing" ||
    connection.health === "not_configured"
  ) {
    return "setup_required";
  }
  if (["degraded", "unavailable"].includes(connection.health)) {
    return "needs_attention";
  }
  return "ready";
}

function accountAddress(name: string): string {
  const prefix = "Inbox - ";
  return name.startsWith(prefix) ? name.slice(prefix.length) : name;
}

export function selectConnectedInbox(
  connections: readonly GenericConnectionRecord[],
): ConnectedInbox | null {
  const connection = connections.find(
    (candidate) => candidate.providerType === "inbox",
  );
  if (!connection) return null;

  return ConnectedInboxSchema.parse({
    id: connection.id,
    name: connection.name,
    accountAddress: accountAddress(connection.name),
    environment: connection.environment,
    status: connectionStatus(connection),
    lastCheckedAt: connection.lastCheckedAt,
    canReadConversations: connection.capabilities.read.includes(
      "conversation_read",
    ),
    canCreateDrafts: connection.capabilities.write.includes("draft_create"),
    version: connection.version,
  });
}

export function withoutInboxConnections<T extends { providerType: string }>(
  connections: readonly T[],
): T[] {
  return connections.filter((connection) => connection.providerType !== "inbox");
}

export function resolveConnectedInboxStatus(
  fallback: ConnectedInbox["status"],
  status: InboxConnectionStatus | null | undefined,
): ConnectedInbox["status"] {
  if (!status) return fallback;
  if (
    status.credentialStatus === "expired" ||
    status.syncStatus === "reauthorize"
  ) {
    return "reconnect_required";
  }
  if (
    status.credentialStatus === "missing" ||
    status.health === "not_configured"
  ) {
    return "setup_required";
  }
  if (
    ["degraded", "unavailable"].includes(status.health) ||
    ["delayed", "failed"].includes(status.syncStatus)
  ) {
    return "needs_attention";
  }
  return "ready";
}

export type ConnectedInbox = z.infer<typeof ConnectedInboxSchema>;
export type InboxThread = z.infer<typeof InboxThreadSchema>;
export type InboxImportResult = z.infer<typeof InboxImportResultSchema>;
export type InboxSyncJob = z.infer<typeof InboxSyncJobSchema>;
export type InboxAuthorizationResult = z.infer<
  typeof InboxAuthorizationResultSchema
>;
export type InboxDraftDelivery = z.infer<typeof InboxDraftDeliverySchema>;
export type InboxConnectionStatus = z.infer<
  typeof InboxConnectionStatusSchema
>;
