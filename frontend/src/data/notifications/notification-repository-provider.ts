import { configuredDataSource } from "@/data/api/data-mode";
import { apiNotificationRepository } from "./api-notification-repository";
import { mockNotificationRepository } from "./mock-notification-repository";

export function getNotificationRepository() {
  return configuredDataSource() === "mock"
    ? mockNotificationRepository
    : apiNotificationRepository;
}
