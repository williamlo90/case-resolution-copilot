import {
  InboxAuthorizationResultSchema,
  InboxConnectionStatusSchema,
  InboxDraftDeliverySchema,
  InboxImportResultSchema,
  InboxSyncJobSchema,
  InboxThreadSchema,
} from "@/domain/connections/connected-inbox";
import { z } from "zod";

export const authorizationStartEnvelopeSchema = z.object({
  data: z.object({
    authorization_url: z.string().url(),
    expires_at: z.string().datetime(),
  }),
});

export const authorizationCompleteEnvelopeSchema = z.object({
  data: z.object({
    connection_id: z.string().min(1),
    account_address: z.string().min(1),
    return_path: z.string().min(1),
    capabilities: z.array(
      z.enum(["conversation_read", "draft_create"]),
    ),
  }),
});

export const inboxThreadListEnvelopeSchema = z.object({
  items: z.array(
    z.object({
      provider_thread_id: z.string().min(1),
      subject: z.string().min(1),
      latest_message_at: z.string().datetime(),
    }),
  ),
  next_cursor: z.string().nullable(),
});

export const inboxStatusEnvelopeSchema = z.object({
  data: z.object({
    connection_public_id: z.string().min(1),
    account_address: z.string().min(1),
    import_mode: z.enum(["paused", "manual", "scheduled"]),
    health: z.enum(["healthy", "degraded", "unavailable", "not_configured"]),
    credential_status: z.enum(["demo", "connected", "missing", "expired"]),
    sync_status: z.enum(["current", "syncing", "delayed", "failed", "reauthorize"]),
    capabilities: z.array(z.string().min(1)),
    last_checked_at: z.string().datetime().nullable(),
    last_successful_sync_at: z.string().datetime().nullable(),
    last_error_code: z.string().min(1).nullable(),
  }),
});

export const inboxImportEnvelopeSchema = z.object({
  data: z.object({
    case_id: z.string().min(1),
    conversation_id: z.string().min(1),
    imported_messages: z.number().int().nonnegative(),
    duplicate_messages: z.number().int().nonnegative(),
    latest_message_at: z.string().datetime(),
  }),
});

export const inboxSyncEnvelopeSchema = z.object({
  data: z.object({
    id: z.string().min(1),
    status: z.enum(["pending", "running", "completed", "failed", "dead"]),
    attempt_count: z.number().int().nonnegative(),
  }),
});

export const inboxControlEnvelopeSchema = z.object({
  data: z.object({
    status: z.enum(["paused", "ready", "disconnected"]),
    provider_revoked: z.boolean().nullable().optional(),
  }),
});

export const inboxDraftEnvelopeSchema = z.object({
  data: z.object({
    id: z.string().min(1),
    status: z.enum([
      "ready",
      "running",
      "completed",
      "failed_safe",
      "outcome_unknown",
      "recovery_required",
    ]),
    attempt_count: z.number().int().nonnegative(),
    provider_draft_id: z.string().min(1).nullable(),
    last_error_code: z.string().min(1).nullable(),
  }),
});

export const inboxDraftLookupEnvelopeSchema = z.object({
  data: inboxDraftEnvelopeSchema.shape.data.nullable(),
});

export function mapAuthorizationResult(
  value: z.infer<typeof authorizationCompleteEnvelopeSchema>["data"],
) {
  return InboxAuthorizationResultSchema.parse({
    connectionId: value.connection_id,
    accountAddress: value.account_address,
    returnPath: value.return_path,
    capabilities: value.capabilities,
  });
}

export function mapInboxStatus(
  value: z.infer<typeof inboxStatusEnvelopeSchema>["data"],
) {
  return InboxConnectionStatusSchema.parse({
    connectionId: value.connection_public_id,
    accountAddress: value.account_address,
    importMode: value.import_mode,
    health: value.health,
    credentialStatus: value.credential_status,
    syncStatus: value.sync_status,
    capabilities: value.capabilities,
    lastCheckedAt: value.last_checked_at,
    lastSuccessfulSyncAt: value.last_successful_sync_at,
    lastErrorCode: value.last_error_code,
  });
}

export function mapThread(
  value: z.infer<typeof inboxThreadListEnvelopeSchema>["items"][number],
) {
  return InboxThreadSchema.parse({
    providerThreadId: value.provider_thread_id,
    subject: value.subject,
    latestMessageAt: value.latest_message_at,
  });
}

export function mapImportResult(
  value: z.infer<typeof inboxImportEnvelopeSchema>["data"],
) {
  return InboxImportResultSchema.parse({
    caseId: value.case_id,
    conversationId: value.conversation_id,
    importedMessages: value.imported_messages,
    duplicateMessages: value.duplicate_messages,
    latestMessageAt: value.latest_message_at,
  });
}

export function mapSyncJob(
  value: z.infer<typeof inboxSyncEnvelopeSchema>["data"],
) {
  return InboxSyncJobSchema.parse({
    id: value.id,
    status: value.status,
    attemptCount: value.attempt_count,
  });
}

export function mapDraftDelivery(
  value: z.infer<typeof inboxDraftEnvelopeSchema>["data"],
) {
  return InboxDraftDeliverySchema.parse({
    id: value.id,
    status: value.status,
    attemptCount: value.attempt_count,
    providerDraftId: value.provider_draft_id,
    lastErrorCode: value.last_error_code,
  });
}
