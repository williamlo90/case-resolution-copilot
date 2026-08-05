import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("@/data/api/api-client", () => ({
  apiRequest: apiRequestMock,
}));

import { apiAdministrationRepository } from "./api-administration-repository";

describe("API administration invitations", () => {
  beforeEach(() => {
    apiRequestMock.mockReset();
  });

  it("maps pending invitations without exposing provider secrets", async () => {
    apiRequestMock.mockResolvedValue({
      items: [
        {
          id: "INV-1001",
          organization_id: "ORG-0001",
          email: "new.supervisor@example.com",
          role: "supervisor",
          status: "pending",
          version: 2,
          invited_by: "USR-0003",
          expires_at: "2026-08-04T03:52:00.000Z",
          accepted_at: null,
        },
      ],
      next_cursor: null,
      total: 1,
    });

    const invitations =
      await apiAdministrationRepository.listInvitations();

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/invitations",
      expect.anything(),
    );
    expect(invitations[0]).toMatchObject({
      id: "INV-1001",
      role: "supervisor",
      status: "pending",
      version: 2,
    });
  });
});
