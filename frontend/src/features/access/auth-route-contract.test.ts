import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const appDirectory = resolve(process.cwd(), "src", "app");

describe("Clerk path routing contract", () => {
  it.each([
    ["sign-in", "[[...sign-in]]"],
    ["invite", "[[...invite]]"],
  ])("keeps /%s as an optional catch-all route", (route, segment) => {
    expect(
      existsSync(resolve(appDirectory, route, segment, "page.tsx")),
    ).toBe(true);
    expect(existsSync(resolve(appDirectory, route, "page.tsx"))).toBe(
      false,
    );
  });
});
