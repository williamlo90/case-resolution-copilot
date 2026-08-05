import { afterEach, describe, expect, it, vi } from "vitest";
import { apiCaseRepository } from "./api-case-repository";

const summary = {
  id: "CS-2048",
  organization_id: "ORG-0001",
  source_id: "SRC-2048",
  external_reference: "INV-88241",
  category: "billing_dispute",
  issue: "Duplicate subscription charge",
  customer: { name: "Maya Chen", is_vip: false },
  status: "investigating",
  owner: { id: "USR-0001", name: "Maya Specialist", initials: "MS" },
  urgency: "high",
  risk: "high",
  sla_minutes_remaining: 42,
  updated_at: "2026-07-23T10:00:00.000Z",
  source_freshness: {
    status: "current",
    checked_at: "2026-07-23T09:59:00.000Z",
  },
  impact: { amount: "99.00", currency: "USD" },
  version: 3,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiCaseRepository", () => {
  it("reads the generic case list rather than the legacy task API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [summary],
          next_cursor: null,
          previous_cursor: null,
          total: 1,
          offset: 0,
          limit: 8,
          summary_scope: "organization",
          summary: {
            total: 1,
            attention: 1,
            review: 0,
            sla_at_risk: 0,
            unassigned: 0,
          },
          meta: { data_mode: "demo", contract_version: "2026-07-22" },
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const page = await apiCaseRepository.listCases();

    expect(page.items[0]).toMatchObject({
      id: "CS-2048",
      sourceId: "SRC-2048",
      impact: { amount: 99, currency: "USD" },
      version: 3,
    });
    expect(page.total).toBe(1);
    expect(fetchMock.mock.calls[0][0]).toContain("limit=8");
    expect(fetchMock.mock.calls[0][0]).toContain("view=all");
    expect(fetchMock.mock.calls[0][0]).toContain("sort=priority");
    expect(fetchMock.mock.calls[0][0]).not.toContain("/api/tasks");
  });

  it("sends global queue filters and opaque cursors to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          next_cursor: "next",
          previous_cursor: "previous",
          total: 113,
          offset: 104,
          limit: 8,
          summary_scope: "organization",
          summary: {
            total: 140,
            attention: 9,
            review: 4,
            sla_at_risk: 3,
            unassigned: 7,
          },
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const page = await apiCaseRepository.listCases({
      query: "payment",
      view: "at_risk",
      status: "investigating",
      category: "billing_dispute",
      sort: "updated",
      cursor: "opaque-page",
      limit: 8,
    });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("query=payment");
    expect(url).toContain("view=at_risk");
    expect(url).toContain("status=investigating");
    expect(url).toContain("category=billing_dispute");
    expect(url).toContain("sort=updated");
    expect(url).toContain("cursor=opaque-page");
    expect(page).toMatchObject({
      offset: 104,
      total: 113,
      previousCursor: "previous",
      nextCursor: "next",
      summaryScope: "organization",
      summary: { total: 140, slaAtRisk: 3 },
    });
  });

  it("accepts a case that has not produced a decision brief yet", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            data: {
              case: summary,
              request: {
                id: "REQ-2048",
                received_at: "2026-07-23T09:00:00.000Z",
                channel: "email",
                customer_message: "I was charged twice.",
                summary: "Duplicate charge requires investigation.",
              },
              conversation: {
                id: "THR-2048",
                organization_id: "ORG-0001",
                case_id: "CS-2048",
                messages: [
                  {
                    id: "MSG-2048",
                    organization_id: "ORG-0001",
                    case_id: "CS-2048",
                    author_type: "customer",
                    author_id: "CUS-2048",
                    author_name: "Maya Chen",
                    channel: "email",
                    body: "I was charged twice.",
                    internal: false,
                    source_reference: "EMAIL-2048",
                    created_at: "2026-07-23T09:00:00.000Z",
                    version: 1,
                  },
                ],
                version: 1,
                updated_at: "2026-07-23T09:00:00.000Z",
              },
              customer: {
                id: "CUS-2048",
                tier: "standard",
                locale: "en-US",
                contact: "customer@example.com",
              },
              business_contexts: [
                {
                  id: "CTX-2048-INVOICE",
                  organization_id: "ORG-0001",
                  case_id: "CS-2048",
                  type: "invoice",
                  label: "Invoice INV-88241",
                  source: "billing_simulator",
                  source_reference: "INV-88241",
                  status: "paid",
                  fields: { total: "USD 99.00" },
                  captured_at: "2026-07-23T09:00:00.000Z",
                  source_freshness: {
                    status: "current",
                    checked_at: "2026-07-23T09:00:00.000Z",
                  },
                  version: 1,
                },
              ],
              facts: [],
              missing_information: [],
              evidence: [],
              risks: [],
              proposal: null,
              response_draft: null,
              proposed_actions: [],
              activity: [],
              available_commands: ["save_draft"],
            },
            meta: { data_mode: "demo", contract_version: "2026-07-22" },
          }),
          { status: 200 },
        ),
      ),
    );

    const workspace = await apiCaseRepository.getCaseWorkspace("CS-2048");

    expect(workspace?.proposal).toBeNull();
    expect(workspace?.responseDraft).toBeNull();
    expect(workspace?.facts).toEqual([]);
    expect(workspace?.conversation.messages[0]).toMatchObject({
      authorName: "Maya Chen",
      body: "I was charged twice.",
    });
    expect(workspace?.collections).toEqual({
      businessContexts: {
        returned: 1,
        total: 1,
        hasMore: false,
        nextCursor: null,
      },
      messages: {
        returned: 1,
        total: 1,
        hasMore: false,
        nextCursor: null,
      },
      activity: {
        returned: 0,
        total: 0,
        hasMore: false,
        nextCursor: null,
      },
    });
    expect(workspace?.availableCommands).toContain("save_draft");
  });
});
