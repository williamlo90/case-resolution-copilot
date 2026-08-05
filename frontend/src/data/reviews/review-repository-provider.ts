import { configuredDataSource } from "@/data/api/data-mode";
import { apiReviewRepository } from "./api-review-repository";
import { mockReviewRepository } from "./mock-review-repository";

export function getReviewRepository() {
  return configuredDataSource() === "mock"
    ? mockReviewRepository
    : apiReviewRepository;
}
