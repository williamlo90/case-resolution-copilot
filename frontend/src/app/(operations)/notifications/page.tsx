import { getNotificationRepository } from "@/data/notifications/notification-repository-provider";
import { NotificationsPage } from "@/features/notifications/components/notifications-page";
import type { Metadata } from "next";
import {
  markAllNotificationsRead,
  markNotificationRead,
} from "../_actions/notifications";

export const metadata: Metadata = { title: "Notifications" };
export const dynamic = "force-dynamic";

export default async function NotificationsRoute() {
  const repository = getNotificationRepository();
  return (
    <NotificationsPage
      notifications={await repository.listNotifications()}
      connected={repository.source === "api"}
      markReadAction={
        repository.source === "api" ? markNotificationRead : undefined
      }
      markAllReadAction={
        repository.source === "api" ? markAllNotificationsRead : undefined
      }
    />
  );
}
