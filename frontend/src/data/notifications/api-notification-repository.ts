import { apiRequest } from "@/data/api/api-client";
import {
  NotificationPageSchema,
  type NotificationPage,
} from "@/domain/notifications/notification";
import { z } from "zod";
import type { NotificationRepository } from "./notification-repository";

const notificationListSchema = z.object({
  items: z.array(
    z.object({
      id: z.string().min(1),
      organization_id: z.string().min(1),
      kind: z.enum([
        "sla_risk",
        "review_waiting",
        "action_recovery",
        "membership_changed",
        "settings_changed",
        "system",
      ]),
      status: z.enum(["unread", "read"]),
      title: z.string().min(1),
      message: z.string().min(1),
      resource_type: z.enum([
        "case",
        "review",
        "action",
        "connection",
        "member",
        "settings",
        "system",
      ]),
      resource_id: z.string().min(1),
      version: z.number().int().positive(),
      created_at: z.string().datetime(),
      read_at: z.string().datetime().nullable(),
    }),
  ),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
  unread_count: z.number().int().nonnegative(),
});

export const apiNotificationRepository: NotificationRepository = {
  source: "api",
  async listNotifications(): Promise<NotificationPage> {
    const response = await apiRequest(
      "/api/notifications?limit=100",
      notificationListSchema,
    );
    return NotificationPageSchema.parse({
      items: response.items.map((item) => ({
        id: item.id,
        kind: item.kind,
        status: item.status,
        title: item.title,
        message: item.message,
        resourceType: item.resource_type,
        resourceId: item.resource_id,
        version: item.version,
        createdAt: item.created_at,
        readAt: item.read_at,
      })),
      total: response.total,
      unreadCount: response.unread_count,
    });
  },
};
