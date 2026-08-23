import { ApiClientError } from "@/data/api/api-client";
import { initialCommandState } from "@/data/commands/command-state";
import { afterEach, describe, expect, it, vi } from "vitest";

const { apiRequestMock, redirectMock, revalidatePathMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
  redirectMock: vi.fn(),
  revalidatePathMock: vi.fn(),
}));

vi.mock("@/data/api/api-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/data/api/api-client")>();
  return {
    ...actual,
    apiRequest: apiRequestMock,
  };
});

vi.mock("next/cache", () => ({
  revalidatePath: revalidatePathMock,
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

import {
  addCaseEvidence,
  addCaseConversationEntry,
  loadCaseActivityHistory,
  loadCaseConversationHistory,
  prepareCaseDecisionBrief,
  updateCaseWorkflow,
} from "./_actions/cases";
import { markNotificationRead } from "./_actions/notifications";
import {
  createPolicy,
  runPolicyLifecycleCommand,
} from "./_actions/policies";
import { revokeInvitation } from "./_actions/team";

function decisionBriefResponse({
  proposalVersion = 2,
  analysisStatus = "completed",
  aiStatus = "completed",
}: {
  proposalVersion?: number;
  analysisStatus?: "completed" | "abstained";
  aiStatus?: "completed" | "abstained";
} = {}) {
  return {
    data: {
      analysis: { status: analysisStatus },
      proposal: { version: proposalVersion },
      checkpoints: [
        {
          step: "ai_narrative",
          status: aiStatus,
        },
      ],
    },
  };
}

describe("prepareCaseDecisionBrief", () => {
  afterEach(() => {
    apiRequestMock.mockReset();
    redirectMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("reports an AI-assisted update and refreshes case data", async () => {
    apiRequestMock.mockResolvedValue(decisionBriefResponse());

    const result = await prepareCaseDecisionBrief(
      "CS-2048",
      4,
      1,
      initialCommandState,
      new FormData(),
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/cases/CS-2048/proposals",
      expect.anything(),
      {
        method: "POST",
        body: { expected_case_version: 4 },
      },
    );
    expect(result).toMatchObject({
      status: "success",
      message: expect.stringContaining("AI drafted the wording"),
    });
    expect(revalidatePathMock).toHaveBeenCalledWith("/cases/CS-2048");
    expect(revalidatePathMock).toHaveBeenCalledWith("/cases");
  });

  it("makes the safe fallback visible without treating it as a failure", async () => {
    apiRequestMock.mockResolvedValue(
      decisionBriefResponse({ aiStatus: "abstained" }),
    );

    const result = await prepareCaseDecisionBrief(
      "CS-2048",
      4,
      1,
      initialCommandState,
      new FormData(),
    );

    expect(result).toMatchObject({
      status: "success",
      tone: "warning",
      message: expect.stringContaining("backup draft"),
    });
  });

  it("does not claim a new result when the existing brief is current", async () => {
    apiRequestMock.mockResolvedValue(
      decisionBriefResponse({ proposalVersion: 1 }),
    );

    const result = await prepareCaseDecisionBrief(
      "CS-2048",
      4,
      1,
      initialCommandState,
      new FormData(),
    );

    expect(result.message).toBe("The decision brief is already up to date.");
  });

  it("returns a useful API error with its support reference", async () => {
    apiRequestMock.mockRejectedValue(
      new ApiClientError(
        "Decision brief could not be prepared.",
        503,
        "decision_brief_failed",
        "corr-test",
      ),
    );

    const result = await prepareCaseDecisionBrief(
      "CS-2048",
      4,
      1,
      initialCommandState,
      new FormData(),
    );

    expect(result).toMatchObject({
      status: "error",
      message: "Decision brief could not be prepared.",
      correlationId: "corr-test",
    });
  });
});

describe("updateCaseWorkflow", () => {
  afterEach(() => {
    apiRequestMock.mockReset();
    redirectMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("requests missing information against the current case version", async () => {
    apiRequestMock.mockResolvedValue({ data: {} });

    const result = await updateCaseWorkflow(
      "CS-2048",
      4,
      "information_needed",
      initialCommandState,
      new FormData(),
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/cases/CS-2048/status",
      expect.anything(),
      {
        method: "POST",
        body: {
          expected_version: 4,
          status: "information_needed",
        },
      },
    );
    expect(result.message).toContain("waiting for more information");
    expect(revalidatePathMock).toHaveBeenCalledWith("/cases/CS-2048");
    expect(revalidatePathMock).toHaveBeenCalledWith("/cases");
  });

  it("starts investigation against the current case version", async () => {
    apiRequestMock.mockResolvedValue({ data: {} });

    const result = await updateCaseWorkflow(
      "CS-2048",
      5,
      "investigating",
      initialCommandState,
      new FormData(),
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/cases/CS-2048/status",
      expect.anything(),
      {
        method: "POST",
        body: {
          expected_version: 5,
          status: "investigating",
        },
      },
    );
    expect(result.message).toContain("under investigation");
  });
});

describe("case conversation commands", () => {
  afterEach(() => {
    apiRequestMock.mockReset();
    redirectMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("records an internal note against the exact case version", async () => {
    apiRequestMock.mockResolvedValue({ data: {} });
    const formData = new FormData();
    formData.set("body", "Customer identity was verified by phone.");

    const result = await addCaseConversationEntry(
      "CS-2048",
      6,
      "note",
      "email",
      initialCommandState,
      formData,
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/cases/CS-2048/notes",
      expect.anything(),
      {
        method: "POST",
        body: {
          expected_case_version: 6,
          body: "Customer identity was verified by phone.",
        },
      },
    );
    expect(result.message).toBe("The internal note was added.");
  });

  it("maps an earlier conversation page without exposing transport fields", async () => {
    apiRequestMock.mockResolvedValue({
      items: [
        {
          id: "MSG-OLDER",
          organization_id: "ORG-0001",
          case_id: "CS-2048",
          author_type: "customer",
          author_id: "CUS-2048",
          author_name: "Maya Chen",
          channel: "email",
          body: "Earlier customer context.",
          internal: false,
          source_reference: "EMAIL-OLDER",
          created_at: "2026-07-20T02:46:00.000Z",
          version: 1,
        },
      ],
      next_cursor: null,
      total: 2,
    });

    const result = await loadCaseConversationHistory(
      "CS-2048",
      "older page",
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/cases/CS-2048/conversation/history?cursor=older+page&limit=50",
      expect.anything(),
    );
    expect(result).toMatchObject({
      status: "success",
      items: [{ id: "MSG-OLDER", authorName: "Maya Chen" }],
      nextCursor: null,
      total: 2,
    });
  });

  it("returns a plain error when earlier activity cannot be loaded", async () => {
    apiRequestMock.mockRejectedValue(
      new ApiClientError(
        "Earlier activity is temporarily unavailable.",
        503,
        "case_history_unavailable",
        "corr-history",
      ),
    );

    const result = await loadCaseActivityHistory(
      "CS-2048",
      "activity-cursor",
    );

    expect(result).toEqual({
      status: "error",
      message: "Earlier activity is temporarily unavailable.",
    });
  });
});

describe("case evidence commands", () => {
  afterEach(() => {
    apiRequestMock.mockReset();
    redirectMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("adds a checked payment record against the exact case version", async () => {
    apiRequestMock.mockResolvedValue({ data: {} });
    const formData = new FormData();
    formData.set("type", "payment");
    formData.set("label", "Second settled charge");
    formData.set("source", "Billing system");
    formData.set("source_reference", "PAY-SECOND");
    formData.set("status", "settled");
    formData.set("amount", "49.00");
    formData.set("currency", "usd");

    const result = await addCaseEvidence(
      "CS-2048",
      6,
      initialCommandState,
      formData,
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/cases/CS-2048/evidence-records",
      expect.anything(),
      {
        method: "POST",
        body: {
          expected_case_version: 6,
          type: "payment",
          label: "Second settled charge",
          source: "Billing system",
          source_reference: "PAY-SECOND",
          status: "settled",
          fields: { amount: "49.00", currency: "USD" },
        },
      },
    );
    expect(result.message).toContain("Checked record added");
    expect(revalidatePathMock).toHaveBeenCalledWith("/cases/CS-2048");
    expect(revalidatePathMock).toHaveBeenCalledWith("/reviews");
  });

  it("rejects an incomplete payment before calling the backend", async () => {
    const formData = new FormData();
    formData.set("type", "payment");
    formData.set("label", "Second charge");
    formData.set("source", "Billing system");
    formData.set("source_reference", "PAY-SECOND");
    formData.set("status", "settled");

    const result = await addCaseEvidence(
      "CS-2048",
      6,
      initialCommandState,
      formData,
    );

    expect(result).toMatchObject({
      status: "error",
      message: expect.stringContaining("amount"),
    });
    expect(apiRequestMock).not.toHaveBeenCalled();
  });
});

describe("notification commands", () => {
  afterEach(() => {
    apiRequestMock.mockReset();
    redirectMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("marks the exact notification version as read", async () => {
    apiRequestMock.mockResolvedValue({ data: {} });

    const result = await markNotificationRead(
      "NTF-1001",
      2,
      initialCommandState,
      new FormData(),
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/notifications/NTF-1001/read",
      expect.anything(),
      {
        method: "POST",
        body: { expected_version: 2 },
      },
    );
    expect(revalidatePathMock).toHaveBeenCalledWith("/notifications");
    expect(result.message).toBe("The notification was marked as read.");
  });
});

describe("team commands", () => {
  afterEach(() => {
    apiRequestMock.mockReset();
    redirectMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("revokes the exact pending invitation version", async () => {
    apiRequestMock.mockResolvedValue({ data: {} });

    const result = await revokeInvitation(
      "INV-1001",
      3,
      initialCommandState,
      new FormData(),
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/invitations/INV-1001/revoke",
      expect.anything(),
      {
        method: "POST",
        body: { expected_version: 3 },
      },
    );
    expect(revalidatePathMock).toHaveBeenCalledWith("/team");
    expect(result.message).toBe("The invitation was revoked.");
  });
});

function policyForm(): FormData {
  const formData = new FormData();
  formData.set("title", "Cancellation policy");
  formData.set("description", "Rules for cancellation requests.");
  formData.set("source_name", "Support handbook");
  formData.set(
    "source_text",
    "## Eligibility\nA verified cancellation request may be reviewed.",
  );
  formData.set("decision_scope", "general_support");
  formData.append("case_categories", "service_exception");
  return formData;
}

describe("policy commands", () => {
  afterEach(() => {
    apiRequestMock.mockReset();
    redirectMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("creates a governed draft and redirects to its detail page", async () => {
    apiRequestMock.mockResolvedValue({
      data: { policy: { id: "POL-CANCELLATION" } },
    });

    await createPolicy(initialCommandState, policyForm());

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/policies",
      expect.anything(),
      expect.objectContaining({
        method: "POST",
        body: expect.objectContaining({
          title: "Cancellation policy",
          applicability: expect.objectContaining({
            case_categories: ["service_exception"],
          }),
        }),
      }),
    );
    expect(redirectMock).toHaveBeenCalledWith(
      "/policies/POL-CANCELLATION",
    );
  });

  it("publishes the exact policy version", async () => {
    apiRequestMock.mockResolvedValue({
      data: { policy: { id: "POL-1008" } },
    });
    const formData = new FormData();
    formData.set("command", "publish");
    formData.set("effective_from", "2026-08-01");

    const result = await runPolicyLifecycleCommand(
      "POL-1008",
      3,
      4,
      2,
      initialCommandState,
      formData,
    );

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/policies/POL-1008/versions/4/publish",
      expect.anything(),
      {
        method: "POST",
        body: {
          expected_policy_version: 3,
          expected_version: 2,
          effective_from: "2026-08-01T00:00:00.000Z",
        },
      },
    );
    expect(result.message).toBe("The policy version was published.");
  });

  it("requires an effective date before scheduling", async () => {
    const formData = new FormData();
    formData.set("command", "schedule");

    const result = await runPolicyLifecycleCommand(
      "POL-1008",
      3,
      4,
      2,
      initialCommandState,
      formData,
    );

    expect(apiRequestMock).not.toHaveBeenCalled();
    expect(result).toMatchObject({
      status: "error",
      message: "Choose a valid effective date.",
    });
  });
});
