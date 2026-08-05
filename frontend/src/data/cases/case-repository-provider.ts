import { configuredDataSource } from "@/data/api/data-mode";
import { apiCaseRepository } from "./api-case-repository";
import type { CaseRepository } from "./case-repository";
import { mockCaseRepository } from "./mock-case-repository";

export function getCaseRepository(): CaseRepository {
  return configuredDataSource() === "mock"
    ? mockCaseRepository
    : apiCaseRepository;
}
