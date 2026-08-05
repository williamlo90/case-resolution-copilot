import { ApiClientError } from "@/data/api/api-client";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("@/data/api/api-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/data/api/api-client")>();
  return {
    ...actual,
    apiRequest: apiRequestMock,
  };
});

import { POST } from "./route";

describe("case audit download route", () => {
  beforeEach(() => {
    apiRequestMock.mockReset();
  });

  it("returns an attachment without exposing backend authentication", async () => {
    apiRequestMock.mockResolvedValue({
      data: {
        case_id: "CS-2048",
        organization_id: "ORG-0001",
        source_id: "support:case-2048",
        external_reference: "EXT-2048",
        legacy_task_id: null,
        generated_at: "2026-07-28T05:00:00.000Z",
        generated_by: "USR-0003",
        governance: null,
        events: [],
      },
    });

    const response = await POST(new Request("http://localhost", { method: "POST" }), {
      params: Promise.resolve({ caseId: "CS-2048" }),
    });

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/cases/CS-2048/audit-export",
      expect.anything(),
      { method: "POST" },
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Disposition")).toBe(
      'attachment; filename="CS-2048-audit.json"',
    );
    expect(await response.json()).toMatchObject({ case_id: "CS-2048" });
  });

  it("preserves a denied export as a denied response", async () => {
    apiRequestMock.mockRejectedValue(
      new ApiClientError(
        "Audit access is not available.",
        403,
        "audit_read_forbidden",
        "corr-test",
      ),
    );

    const response = await POST(new Request("http://localhost", { method: "POST" }), {
      params: Promise.resolve({ caseId: "CS-2048" }),
    });

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({
      error: {
        code: "audit_read_forbidden",
        message: "Audit access is not available.",
        correlation_id: "corr-test",
      },
    });
  });
});
