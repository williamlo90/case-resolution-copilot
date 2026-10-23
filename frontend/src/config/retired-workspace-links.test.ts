import { describe, expect, it } from "vitest";
import { retiredWorkspaceDestination } from "./retired-workspace-links";

describe("retired workspace bookmarks", () => {
  it.each([
    "/demo/v2", "/demo/v2/session", "/cases?practice=VD-OLD",
    "/cases/CS-DEMO-OLD?practice=VD-OLD&tab=resolution",
    "/reviews/RV-OLD?practice=VD-OLD", "/actions/AC-OLD?practice=VD-OLD",
    "/policies/POL-OLD?practice=VD-OLD",
  ])("returns %s to the queue without a redirect loop", (path) => {
    const destination = retiredWorkspaceDestination(new URL(path, "https://app.example"));
    expect(destination?.href).toBe("https://app.example/cases");
    expect(retiredWorkspaceDestination(destination!)).toBeNull();
  });

  it.each(["/cases/CS-2047", "/cases?q=billing", "/reviews/RV-1", "/sign-in", "/__clerk/callback"])(
    "preserves normal navigation and authentication at %s", (path) => {
      expect(retiredWorkspaceDestination(new URL(path, "https://app.example"))).toBeNull();
    },
  );
});
