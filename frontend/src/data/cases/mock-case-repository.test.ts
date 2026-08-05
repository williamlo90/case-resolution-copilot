import { describe, expect, it } from "vitest";
import { mockCaseRepository } from "./mock-case-repository";

describe("mockCaseRepository", () => {
  it("supports deterministic risk and SLA ordering", async () => {
    const page = await mockCaseRepository.listCases({ sort: "priority" });

    expect(page.items.length).toBeGreaterThan(1);
    expect(page.items[0].risk).toBe("high");
    expect(page.total).toBeGreaterThanOrEqual(page.items.length);
  });

  it("returns isolated workspace copies", async () => {
    const first = await mockCaseRepository.getCaseWorkspace("CS-2048");
    const second = await mockCaseRepository.getCaseWorkspace("CS-2048");

    expect(first).not.toBeNull();
    expect(second).toEqual(first);
    expect(second).not.toBe(first);
  });

  it("returns only the deterministic actor's cases for the mine view", async () => {
    const page = await mockCaseRepository.listCases({ view: "mine", limit: 20 });

    expect(page.items.length).toBeGreaterThan(0);
    expect(page.items.every((item) => item.owner?.id === "USR-AR")).toBe(true);
  });

  it("uses a stable case id tie-breaker", async () => {
    const first = await mockCaseRepository.listCases({ sort: "priority", limit: 20 });
    const second = await mockCaseRepository.listCases({ sort: "priority", limit: 20 });

    expect(second.items.map((item) => item.id)).toEqual(
      first.items.map((item) => item.id),
    );
  });
});
