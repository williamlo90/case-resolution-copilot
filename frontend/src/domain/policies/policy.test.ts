import { policyDetailFixtures, policySummaryFixtures, publishedPolicyFixture } from "@/mocks/fixtures/policy-fixtures";
import { describe, expect, it } from "vitest";
import { PolicyDetailSchema, PolicySummarySchema } from "./policy";

describe("policy contract", () => {
  it("covers the required policy lifecycle states", () => {
    const policies = PolicySummarySchema.array().parse(policySummaryFixtures);
    expect(new Set(policies.map((item) => item.status))).toEqual(new Set(["draft", "in_review", "published", "scheduled", "retired", "expired", "conflicting", "parsing_failed"]));
    expect(PolicyDetailSchema.array().parse(policyDetailFixtures)).toHaveLength(8);
  });

  it("keeps published and historical versions immutable", () => {
    expect(publishedPolicyFixture.versions.every((item) => item.immutable)).toBe(true);
    expect(publishedPolicyFixture.availableCommands).toContain("create_draft");
  });
});
