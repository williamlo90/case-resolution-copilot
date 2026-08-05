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
});
