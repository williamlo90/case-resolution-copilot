import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("@/data/api/api-client", () => ({
  apiRequest: apiRequestMock,
}));

import { apiNotificationRepository } from "./api-notification-repository";

describe("apiNotificationRepository", () => {
  beforeEach(() => {
    apiRequestMock.mockReset();
  });

  it("maps the backend notification contract", async () => {
    apiRequestMock.mockResolvedValue({
      items: [
        {
          id: "NTF-1001",
          organization_id: "ORG-0001",
          kind: "review_waiting",
          status: "unread",
          title: "Review waiting",
          message: "Review REV-1001 is ready.",
          resource_type: "review",
          resource_id: "REV-1001",
          version: 2,
          created_at: "2026-07-28T05:00:00.000Z",
          read_at: null,
        },
      ],
      next_cursor: null,
      total: 1,
      unread_count: 1,
    });

    const notifications =
      await apiNotificationRepository.listNotifications();

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/notifications?limit=100",
      expect.anything(),
    );
    expect(notifications).toMatchObject({
      unreadCount: 1,
      items: [
        {
          id: "NTF-1001",
          resourceType: "review",
          resourceId: "REV-1001",
          version: 2,
        },
      ],
    });
  });
});
