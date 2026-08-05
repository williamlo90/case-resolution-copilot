import { configuredDataSource } from "@/data/api/data-mode";
import { apiAdministrationRepository } from "./api-administration-repository";
import { mockAdministrationRepository } from "./mock-administration-repository";

export function getAdministrationRepository() {
  return configuredDataSource() === "mock"
    ? mockAdministrationRepository
    : apiAdministrationRepository;
}
