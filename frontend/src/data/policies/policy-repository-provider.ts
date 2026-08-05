import { configuredDataSource } from "@/data/api/data-mode";
import { apiPolicyRepository } from "./api-policy-repository";
import { mockPolicyRepository } from "./mock-policy-repository";
export function getPolicyRepository() {
  return configuredDataSource() === "mock"
    ? mockPolicyRepository
    : apiPolicyRepository;
}
