import { AppShell } from "@/components/layout/app-shell";
import { CaseWorkspace } from "@/features/cases/components/case-workspace";
import { primaryCaseWorkspaceFixture } from "@/mocks/fixtures/case-fixtures";
import { render } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/cases/CS-2048",
}));

describe("protected workspace accessibility", () => {
  it("has no serious or critical axe violations in the primary decision view", async () => {
    render(
      <AppShell
        context={{
          actor: {
            id: "USR-0001",
            organizationId: "ORG-0001",
            name: "Maya Specialist",
            role: "specialist",
            permissions: ["case:read", "review:read", "action:read"],
            authenticationMode: "deterministic_development",
          },
          organization: {
            id: "ORG-0001",
            name: "Northstar Cloud",
            slug: "northstar-cloud",
            version: 1,
            locale: "en-US",
            timeZone: "Asia/Jakarta",
          },
        }}
      >
        <CaseWorkspace workspace={primaryCaseWorkspaceFixture} />
      </AppShell>,
    );

    const result = await axe.run(document.body, {
      // JSDOM has no canvas-backed color computation; hosted visual QA owns contrast.
      rules: { "color-contrast": { enabled: false } },
    });
    const seriousViolations = result.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    );

    expect(
      seriousViolations.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        targets: violation.nodes.map((node) => node.target),
      })),
    ).toEqual([]);
  });
});
