import { afterEach, describe, expect, it, vi } from "vitest";
import { apiConnectedInboxRepository } from "./api-connected-inbox-repository";
import { apiInboxDraftRepository } from "./api-inbox-draft-repository";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("connected inbox API contracts", () => {
  it("maps the stable status read model for paused and recovery UI", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            data: {
              connection_public_id: "CON-INBOX-1",
              account_address: "support@example.com",
              import_mode: "paused",
              health: "degraded",
              credential_status: "connected",
              sync_status: "delayed",
              capabilities: ["conversation_read", "draft_create"],
              last_checked_at: "2026-08-14T08:00:00.000Z",
              last_successful_sync_at: "2026-08-14T07:00:00.000Z",
              last_error_code: "provider_timeout",
            },
          }),
          { status: 200 },
        ),
      ),
    );

    await expect(
      apiConnectedInboxRepository.getStatus("CON-INBOX-1"),
    ).resolves.toMatchObject({
      connectionId: "CON-INBOX-1",
      importMode: "paused",
      syncStatus: "delayed",
      lastErrorCode: "provider_timeout",
    });
  });

  it("maps thread transport fields only after validating the envelope", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              provider_thread_id: "thread-42",
              subject: "Delivery issue",
              latest_message_at: "2026-08-14T08:00:00.000Z",
            },
          ],
          next_cursor: "next-page",
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiConnectedInboxRepository.listThreads("CON-INBOX-1"),
    ).resolves.toEqual({
      items: [
        {
          providerThreadId: "thread-42",
          subject: "Delivery issue",
          latestMessageAt: "2026-08-14T08:00:00.000Z",
        },
      ],
      nextCursor: "next-page",
    });
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/api/connections/CON-INBOX-1/inbox/threads?limit=5",
    );
  });

  it("binds the expected saved-draft version to delivery", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            id: "DDL-1",
            status: "outcome_unknown",
            attempt_count: 1,
            provider_draft_id: null,
            last_error_code: "provider_timeout",
          },
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const delivery = await apiInboxDraftRepository.deliver("CS-42", 7);

    expect(delivery).toMatchObject({
      id: "DDL-1",
      status: "outcome_unknown",
      attemptCount: 1,
    });
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.method).toBe("POST");
    expect(JSON.parse(String(request.body))).toEqual({
      expected_draft_version: 7,
    });
  });

  it("restores the latest persisted draft outcome for recovery after refresh", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            data: {
              id: "DDL-PERSISTED",
              status: "outcome_unknown",
              attempt_count: 1,
              provider_draft_id: null,
              last_error_code: "provider_timeout",
            },
          }),
          { status: 200 },
        ),
      ),
    );

    await expect(
      apiInboxDraftRepository.getLatest("CS-42", 3),
    ).resolves.toMatchObject({
      id: "DDL-PERSISTED",
      status: "outcome_unknown",
    });
  });

  it("rejects malformed backend data instead of leaking it into the UI", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ items: [{ subject: "Missing identifiers" }] }),
          { status: 200 },
        ),
      ),
    );

    await expect(
      apiConnectedInboxRepository.listThreads("CON-INBOX-1"),
    ).rejects.toMatchObject({
      code: "invalid_backend_response",
    });
  });
});
