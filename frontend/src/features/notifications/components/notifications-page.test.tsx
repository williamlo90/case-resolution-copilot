import type { NotificationPage as NotificationPageModel } from "@/domain/notifications/notification";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NotificationsPage } from "./notifications-page";

const notifications: NotificationPageModel = {
  items: [
    {
      id: "NTF-1001",
      kind: "review_waiting",
      status: "unread",
      title: "Review waiting",
      message: "Review REV-1001 is ready.",
      resourceType: "review",
      resourceId: "REV-1001",
      version: 2,
      createdAt: "2026-07-28T05:00:00.000Z",
      readAt: null,
    },
  ],
  total: 1,
  unreadCount: 1,
};

describe("NotificationsPage", () => {
  it("opens the related work and records a read command", async () => {
    render(
      <NotificationsPage
        notifications={notifications}
        connected
        markReadAction={async () => ({
          status: "success",
          message: "The notification was marked as read.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
      />,
    );

    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "/reviews/REV-1001",
    );
    fireEvent.click(screen.getByRole("button", { name: "Mark as read" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "marked as read",
    );
  });

  it("shows a useful empty state", () => {
    render(
      <NotificationsPage
        notifications={{ items: [], total: 0, unreadCount: 0 }}
        connected
      />,
    );

    expect(
      screen.getByRole("heading", { name: "No notifications" }),
    ).toBeVisible();
  });
});
