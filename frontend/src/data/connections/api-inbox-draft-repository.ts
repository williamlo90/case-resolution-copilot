import { apiRequest } from "@/data/api/api-client";
import type { InboxDraftRepository } from "./connected-inbox-repository";
import {
  inboxDraftEnvelopeSchema,
  inboxDraftLookupEnvelopeSchema,
  mapDraftDelivery,
} from "./inbox-transport";

export const apiInboxDraftRepository: InboxDraftRepository = {
  async getLatest(caseId, expectedDraftVersion) {
    const parameters = new URLSearchParams({
      draft_version: String(expectedDraftVersion),
    });
    const response = await apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/response-draft/delivery?${parameters}`,
      inboxDraftLookupEnvelopeSchema,
    );
    return response.data ? mapDraftDelivery(response.data) : null;
  },

  async deliver(caseId, expectedDraftVersion) {
    const response = await apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/response-draft/deliver`,
      inboxDraftEnvelopeSchema,
      {
        method: "POST",
        body: { expected_draft_version: expectedDraftVersion },
      },
    );
    return mapDraftDelivery(response.data);
  },

  async reconcile(deliveryId) {
    const response = await apiRequest(
      `/api/draft-deliveries/${encodeURIComponent(deliveryId)}/reconcile`,
      inboxDraftEnvelopeSchema,
      { method: "POST" },
    );
    return mapDraftDelivery(response.data);
  },
};
