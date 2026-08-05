import { z } from "zod";

export const NotificationSchema = z.object({
  id: z.string().min(1),
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
  resourceType: z.enum([
    "case",
    "review",
    "action",
    "connection",
    "member",
    "settings",
    "system",
  ]),
  resourceId: z.string().min(1),
  version: z.number().int().positive(),
  createdAt: z.string().datetime(),
  readAt: z.string().datetime().nullable(),
});

export const NotificationPageSchema = z.object({
  items: z.array(NotificationSchema),
  total: z.number().int().nonnegative(),
  unreadCount: z.number().int().nonnegative(),
});

export type Notification = z.infer<typeof NotificationSchema>;
export type NotificationPage = z.infer<typeof NotificationPageSchema>;
