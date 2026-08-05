import { configuredDataSource } from "@/data/api/data-mode";
import { apiActionRepository } from "./api-action-repository";
import { mockActionRepository } from "./mock-action-repository";

export function getActionRepository() {
  return configuredDataSource() === "mock"
    ? mockActionRepository
    : apiActionRepository;
}
