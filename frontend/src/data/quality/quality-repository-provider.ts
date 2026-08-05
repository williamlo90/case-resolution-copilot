import { configuredDataSource } from "@/data/api/data-mode";
import { apiQualityRepository } from "./api-quality-repository";
import { mockQualityRepository } from "./mock-quality-repository";

export function getQualityRepository() {
  return configuredDataSource() === "mock"
    ? mockQualityRepository
    : apiQualityRepository;
}
