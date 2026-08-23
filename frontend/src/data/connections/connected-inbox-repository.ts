import type {
  InboxAuthorizationResult,
  InboxConnectionStatus,
  InboxDraftDelivery,
  InboxImportResult,
  InboxSyncJob,
  InboxThread,
} from "@/domain/connections/connected-inbox";

export type InboxAuthorizationStart = {
  authorizationUrl: string;
  expiresAt: string;
};

export type InboxThreadPage = {
  items: InboxThread[];
  nextCursor: string | null;
};

export type InboxImportInput = {
  providerThreadId: string;
  category:
    | "billing_dispute"
    | "refund_request"
    | "account_access"
    | "service_exception";
  urgency: "low" | "medium" | "high" | "critical";
  risk: "low" | "medium" | "high";
  dueAt: string;
};

export type InboxControlResult = {
  status: "paused" | "ready" | "disconnected";
  providerRevoked: boolean | null;
};

export interface InboxAuthorizationRepository {
  start(includeDrafts: boolean): Promise<InboxAuthorizationStart>;
  complete(state: string, code: string): Promise<InboxAuthorizationResult>;
}

export interface ConnectedInboxRepository {
  getStatus(connectionId: string): Promise<InboxConnectionStatus>;
  listThreads(
    connectionId: string,
    cursor?: string | null,
  ): Promise<InboxThreadPage>;
  importThread(
    connectionId: string,
    input: InboxImportInput,
  ): Promise<InboxImportResult>;
  requestSync(connectionId: string): Promise<InboxSyncJob>;
  pause(connectionId: string): Promise<InboxControlResult>;
  resume(connectionId: string): Promise<InboxControlResult>;
  disconnect(connectionId: string): Promise<InboxControlResult>;
}

export interface InboxDraftRepository {
  getLatest(
    caseId: string,
    expectedDraftVersion: number,
  ): Promise<InboxDraftDelivery | null>;
  deliver(
    caseId: string,
    expectedDraftVersion: number,
  ): Promise<InboxDraftDelivery>;
  reconcile(deliveryId: string): Promise<InboxDraftDelivery>;
}
