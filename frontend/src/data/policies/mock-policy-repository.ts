import { policyDetailFixtures, policySummaryFixtures } from "@/mocks/fixtures/policy-fixtures";
import type { PolicyRepository } from "./policy-repository";
export const mockPolicyRepository: PolicyRepository = { source: "mock", async listPolicies() { return policySummaryFixtures; }, async getPolicyDetail(id) { return policyDetailFixtures.find((item) => item.policy.id === id) ?? null; } };
