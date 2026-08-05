import { describe, expect, it, vi } from "vitest";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("@/data/api/api-client", () => ({
  apiRequest: apiRequestMock,
}));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    cache: <Arguments extends unknown[], Result>(
      operation: (...arguments_: Arguments) => Result,
    ) => {
      let result: Result | undefined;
      return (...arguments_: Arguments) => {
        result ??= operation(...arguments_);
        return result;
      };
    },
  };
});

import { apiAdministrationRepository } from "./api-administration-repository";

describe("API administration repository request cache", () => {
  it("shares session context work across one server render", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path === "/api/session") {
        return Promise.resolve({
          data: {
            id: "USR-0003",
            organization_id: "ORG-001",
            name: "Ari Supervisor",
            role: "supervisor",
            permissions: ["case:read"],
            authentication_mode: "provider",
            organization: {
              id: "ORG-001",
              name: "Northstar Support",
              slug: "northstar-support",
              version: 1,
              locale: "en-US",
              time_zone: "Asia/Jakarta",
            },
          },
        });
      }
      if (path === "/api/organizations/current") {
        return Promise.resolve({
          data: {
            id: "ORG-001",
            name: "Northstar Support",
            slug: "northstar-support",
            version: 1,
          },
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    const [first, second] = await Promise.all([
      apiAdministrationRepository.getSessionContext(),
      apiAdministrationRepository.getSessionContext(),
    ]);

    expect(first).toEqual(second);
    expect(apiRequestMock).toHaveBeenCalledTimes(1);
  });
});
