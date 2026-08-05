import { configuredDataSource } from "@/data/api/data-mode";
import { apiCaseRepository } from "./api-case-repository";
import type { CaseRepository } from "./case-repository";
import { mockCaseRepository } from "./mock-case-repository";

let repositoryOverride: CaseRepository | null = null;

export function getCaseRepository(): CaseRepository {
  if (repositoryOverride) return repositoryOverride;
  return configuredDataSource() === "api"
    ? apiCaseRepository
    : mockCaseRepository;
}

export function setCaseRepositoryForTests(next: CaseRepository): () => void {
  const previous = repositoryOverride;
  repositoryOverride = next;
  return () => {
    repositoryOverride = previous;
  };
}
