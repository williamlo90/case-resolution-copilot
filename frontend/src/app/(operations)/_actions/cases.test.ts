import { initialCommandState } from "@/data/commands/command-state";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiRequestMock, revalidatePathMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
  revalidatePathMock: vi.fn(),
}));

vi.mock("@/data/api/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/data/api/api-client")>();
  return { ...actual, apiRequest: apiRequestMock };
});

vi.mock("next/cache", () => ({
  revalidatePath: revalidatePathMock,
}));

import { analyzeCase } from "./cases";

function analysisResult(proposalVersion = 1) {
  return {
    data: {
      analysis: { status: "completed" },
      proposal: { version: proposalVersion },
      checkpoints: [{ step: "ai_narrative", status: "completed" }],
    },
  };
}

describe("analyzeCase", () => {
  beforeEach(() => {
    apiRequestMock.mockReset();
    revalidatePathMock.mockReset();
  });

  it("claims a new case, starts investigation, and analyzes the latest version", async () => {
    apiRequestMock
      .mockResolvedValueOnce({ data: { case: { version: 4 } } })
      .mockResolvedValueOnce({ data: { case: { version: 5 } } })
      .mockResolvedValueOnce(analysisResult());

    const result = await analyzeCase(
      "CS-NEW-1",
      3,
      0,
      true,
      initialCommandState,
      new FormData(),
    );

    expect(apiRequestMock).toHaveBeenNthCalledWith(
      1,
      "/api/cases/CS-NEW-1/assign",
      expect.anything(),
      { method: "POST", body: { expected_version: 3 } },
    );
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      "/api/cases/CS-NEW-1/status",
      expect.anything(),
      {
        method: "POST",
        body: { expected_version: 4, status: "investigating" },
      },
    );
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      3,
      "/api/cases/CS-NEW-1/proposals",
      expect.anything(),
      { method: "POST", body: { expected_case_version: 5 } },
    );
    expect(result).toMatchObject({
      status: "success",
      message: expect.stringContaining("Case analyzed"),
    });
    expect(revalidatePathMock).toHaveBeenCalledWith("/cases/CS-NEW-1");
  });

  it("reanalyzes new information without claiming an owned case again", async () => {
    apiRequestMock
      .mockResolvedValueOnce({ data: { case: { version: 8 } } })
      .mockResolvedValueOnce(analysisResult(3));

    await analyzeCase(
      "CS-WAITING-1",
      7,
      2,
      false,
      initialCommandState,
      new FormData(),
    );

    expect(apiRequestMock).toHaveBeenCalledTimes(2);
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      1,
      "/api/cases/CS-WAITING-1/status",
      expect.anything(),
      {
        method: "POST",
        body: { expected_version: 7, status: "investigating" },
      },
    );
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      "/api/cases/CS-WAITING-1/proposals",
      expect.anything(),
      { method: "POST", body: { expected_case_version: 8 } },
    );
  });

  it("leaves a clear retry path when analysis fails after work starts", async () => {
    apiRequestMock
      .mockResolvedValueOnce({ data: { case: { version: 6 } } })
      .mockRejectedValueOnce(new Error("analysis unavailable"));

    const result = await analyzeCase(
      "CS-NEW-2",
      5,
      0,
      false,
      initialCommandState,
      new FormData(),
    );

    expect(result).toMatchObject({
      status: "error",
      message: expect.stringContaining("Select Analyze case to try again"),
    });
    expect(revalidatePathMock).toHaveBeenCalledWith("/cases/CS-NEW-2");
  });
});
