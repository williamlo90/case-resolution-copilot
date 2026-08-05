import type { PolicyDetail, PolicySummary } from "@/domain/policies/policy";
export interface PolicyRepository { readonly source: "api" | "mock"; listPolicies(): Promise<readonly PolicySummary[]>; getPolicyDetail(id: string): Promise<PolicyDetail | null>; }
