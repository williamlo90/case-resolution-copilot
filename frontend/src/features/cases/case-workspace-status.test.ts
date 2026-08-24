import { primaryCaseWorkspaceFixture } from "@/mocks/fixtures/case-fixtures";
import { describe, expect, it } from "vitest";
import { resolveCaseWorkspaceStatus } from "./case-workspace-status";

describe("resolveCaseWorkspaceStatus", () => {
  it("keeps the operational case status before approval", () => {
    expect(
      resolveCaseWorkspaceStatus(primaryCaseWorkspaceFixture, null),
    ).toEqual({ label: "Needs review", tone: "warning" });
  });

  it("shows an approved draft without changing the case state", () => {
    const workspace = {
      ...primaryCaseWorkspaceFixture,
      proposal: {
        ...primaryCaseWorkspaceFixture.proposal!,
        state: "approved" as const,
      },
    };

    expect(resolveCaseWorkspaceStatus(workspace, null)).toEqual({
      label: "Approved, draft ready",
      tone: "success",
    });
    expect(workspace.case.status).toBe("needs_review");
  });

  it("surfaces the latest Gmail draft outcome after approval", () => {
    const workspace = {
      ...primaryCaseWorkspaceFixture,
      proposal: {
        ...primaryCaseWorkspaceFixture.proposal!,
        state: "approved" as const,
      },
    };

    expect(
      resolveCaseWorkspaceStatus(workspace, {
        id: "DDL-1",
        status: "completed",
        attemptCount: 1,
        providerDraftId: "gmail-draft-1",
        lastErrorCode: null,
      }),
    ).toEqual({ label: "Approved, Gmail draft ready", tone: "success" });
  });
});
