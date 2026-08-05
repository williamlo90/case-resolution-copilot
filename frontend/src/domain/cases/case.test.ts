import { describe, expect, it } from "vitest";
import { CaseSummarySchema, CaseWorkspaceSchema } from "./case";
import { caseSummaryFixtures, primaryCaseWorkspaceFixture } from "@/mocks/fixtures/case-fixtures";

describe("generic case contract", () => {
  it("accepts explicit generic case fixtures", () => {
    expect(CaseSummarySchema.array().parse(caseSummaryFixtures)).toHaveLength(9);
    expect(CaseWorkspaceSchema.parse(primaryCaseWorkspaceFixture).case.id).toBe("CS-2048");
  });

  it("does not accept legacy task identifiers as public case IDs", () => {
    expect(CaseSummarySchema.safeParse({ ...caseSummaryFixtures[0], id: "RF-1042" }).success).toBe(false);
  });
});
