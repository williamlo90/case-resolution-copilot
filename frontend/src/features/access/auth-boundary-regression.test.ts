import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const sourceRoot = resolve(process.cwd(), "src");

describe("Clerk authentication boundary", () => {
  it("does not redirect Next.js data requests from global middleware", () => {
    const proxySource = readFileSync(
      resolve(sourceRoot, "proxy.ts"),
      "utf8",
    );

    expect(proxySource).not.toContain("createRouteMatcher");
    expect(proxySource).not.toContain("auth.protect");
    expect(proxySource).toContain("clerkMiddleware({");
    expect(proxySource).toContain("contentSecurityPolicy");
    expect(proxySource).toContain("strict: true");
  });

  it("keeps the operations layout fail-closed for unauthenticated users", () => {
    const layoutSource = readFileSync(
      resolve(sourceRoot, "app", "(operations)", "layout.tsx"),
      "utf8",
    );

    expect(layoutSource).toContain("error.status === 401");
    expect(layoutSource).toContain('redirect("/sign-in")');
  });

  it("keeps a role denial separate from missing workspace membership", () => {
    const apiClientSource = readFileSync(
      resolve(sourceRoot, "data", "api", "api-client.ts"),
      "utf8",
    );
    const newPolicySource = readFileSync(
      resolve(
        sourceRoot,
        "app",
        "(operations)",
        "policies",
        "new",
        "page.tsx",
      ),
      "utf8",
    );

    expect(apiClientSource).toContain(
      'error.code === "workspace_access_denied"',
    );
    expect(apiClientSource).toContain('redirect("/access-denied")');
    expect(apiClientSource).toContain('redirect("/permission-denied")');
    expect(newPolicySource).toContain('redirect("/permission-denied")');
    expect(newPolicySource).not.toContain('redirect("/access-denied")');
  });

  it("keeps Clerk's internal route inside the middleware matcher", () => {
    const proxySource = readFileSync(
      resolve(sourceRoot, "proxy.ts"),
      "utf8",
    );

    expect(proxySource).toContain('"/__clerk/(.*)"');
  });

  it("keeps Clerk dynamic when the strict nonce policy is enabled", () => {
    const layoutSource = readFileSync(
      resolve(sourceRoot, "app", "layout.tsx"),
      "utf8",
    );

    expect(layoutSource).toMatch(/<ClerkProvider\s+dynamic/);
  });

  it("never sends an already signed-in user through Clerk's account host", () => {
    const signInSource = readFileSync(
      resolve(
        sourceRoot,
        "features",
        "access",
        "components",
        "sign-in-page.tsx",
      ),
      "utf8",
    );

    expect(signInSource).not.toContain("redirectWithAuth");
    expect(signInSource).not.toContain("buildUrlWithAuth");
    expect(signInSource).toContain('replaceDocument("/cases")');
  });
});
