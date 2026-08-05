import {
  NotificationPageSchema,
  type NotificationPage,
} from "@/domain/notifications/notification";
import type { NotificationRepository } from "./notification-repository";

const notifications: NotificationPage = NotificationPageSchema.parse({
  items: [
    {
      id: "NTF-DEMO-1",
      kind: "sla_risk",
      status: "unread",
      title: "Case response limit needs attention",
      message: "Case CS-2048 is approaching its response limit.",
      resourceType: "case",
      resourceId: "CS-2048",
      version: 1,
      createdAt: "2026-07-21T04:30:00.000Z",
      readAt: null,
    },
  ],
  total: 1,
  unreadCount: 1,
});

export const mockNotificationRepository: NotificationRepository = {
  source: "mock",
  async listNotifications() {
    return structuredClone(notifications);
  },
};
