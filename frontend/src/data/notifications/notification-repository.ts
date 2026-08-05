import type { NotificationPage } from "@/domain/notifications/notification";

export interface NotificationRepository {
  readonly source: "api" | "mock";
  listNotifications(): Promise<NotificationPage>;
}
