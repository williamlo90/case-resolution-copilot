import { apiRequest } from "@/data/api/api-client";
import type { ConnectedInboxRepository } from "./connected-inbox-repository";
import {
  inboxControlEnvelopeSchema,
  inboxImportEnvelopeSchema,
  inboxStatusEnvelopeSchema,
  inboxSyncEnvelopeSchema,
  inboxThreadListEnvelopeSchema,
  mapImportResult,
  mapInboxStatus,
  mapSyncJob,
  mapThread,
} from "./inbox-transport";

function connectionPath(connectionId: string, suffix = ""): string {
  return `/api/connections/${encodeURIComponent(connectionId)}${suffix}`;
}

export const apiConnectedInboxRepository: ConnectedInboxRepository = {
  async getStatus(connectionId) {
    const response = await apiRequest(
      connectionPath(connectionId, "/inbox/status"),
      inboxStatusEnvelopeSchema,
    );
    return mapInboxStatus(response.data);
  },

  async listThreads(connectionId, cursor = null) {
    const parameters = new URLSearchParams({ limit: "5" });
    if (cursor) parameters.set("cursor", cursor);
    const response = await apiRequest(
      `${connectionPath(connectionId, "/inbox/threads")}?${parameters}`,
      inboxThreadListEnvelopeSchema,
    );
    return {
      items: response.items.map(mapThread),
      nextCursor: response.next_cursor,
    };
  },

  async importThread(connectionId, input) {
    const response = await apiRequest(
      connectionPath(connectionId, "/imports"),
      inboxImportEnvelopeSchema,
      {
        method: "POST",
        body: {
          provider_thread_id: input.providerThreadId,
          category: input.category,
          urgency: input.urgency,
          risk: input.risk,
          due_at: input.dueAt,
        },
      },
    );
    return mapImportResult(response.data);
  },

  async requestSync(connectionId) {
    const response = await apiRequest(
      connectionPath(connectionId, "/sync"),
      inboxSyncEnvelopeSchema,
      { method: "POST" },
    );
    return mapSyncJob(response.data);
  },

  async pause(connectionId) {
    const response = await apiRequest(
      connectionPath(connectionId, "/pause"),
      inboxControlEnvelopeSchema,
      { method: "POST" },
    );
    return {
      status: response.data.status,
      providerRevoked: response.data.provider_revoked ?? null,
    };
  },

  async resume(connectionId) {
    const response = await apiRequest(
      connectionPath(connectionId, "/resume"),
      inboxControlEnvelopeSchema,
      { method: "POST" },
    );
    return {
      status: response.data.status,
      providerRevoked: response.data.provider_revoked ?? null,
    };
  },

  async disconnect(connectionId) {
    const response = await apiRequest(
      connectionPath(connectionId),
      inboxControlEnvelopeSchema,
      { method: "DELETE" },
    );
    return {
      status: response.data.status,
      providerRevoked: response.data.provider_revoked ?? null,
    };
  },
};
