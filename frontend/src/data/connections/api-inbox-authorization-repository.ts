import { apiRequest } from "@/data/api/api-client";
import type { InboxAuthorizationRepository } from "./connected-inbox-repository";
import {
  authorizationCompleteEnvelopeSchema,
  authorizationStartEnvelopeSchema,
  mapAuthorizationResult,
} from "./inbox-transport";

export const apiInboxAuthorizationRepository: InboxAuthorizationRepository = {
  async start(includeDrafts) {
    const response = await apiRequest(
      "/api/connections/inbox/authorize",
      authorizationStartEnvelopeSchema,
      {
        method: "POST",
        body: { include_drafts: includeDrafts, return_path: "/connections" },
      },
    );
    return {
      authorizationUrl: response.data.authorization_url,
      expiresAt: response.data.expires_at,
    };
  },

  async complete(state, code) {
    const response = await apiRequest(
      "/api/connections/inbox/callback",
      authorizationCompleteEnvelopeSchema,
      { method: "POST", body: { state, code } },
    );
    return mapAuthorizationResult(response.data);
  },
};
