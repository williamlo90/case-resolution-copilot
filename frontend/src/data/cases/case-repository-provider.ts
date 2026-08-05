import type { CaseRepository } from "./case-repository";
import { mockCaseRepository } from "./mock-case-repository";

let repository: CaseRepository = mockCaseRepository;

export function getCaseRepository(): CaseRepository {
  return repository;
}

export function setCaseRepositoryForTests(next: CaseRepository): () => void {
  const previous = repository;
  repository = next;
  return () => {
    repository = previous;
  };
}
