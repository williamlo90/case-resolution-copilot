import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/cases",
}));

describe("AppShell", () => {
  it("exposes the primary landmark and preview boundary", () => {
    render(
      <AppShell
        context={{
          actor: {
            id: "USR-0003",
            organizationId: "ORG-0001",
            name: "Ari Administrator",
            role: "administrator",
            permissions: [
              "case:read",
              "review:read",
              "action:read",
              "policy:read",
              "quality:read",
              "connection:read",
              "member:read",
              "settings:manage",
            ],
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
        <h1>Cases</h1>
      </AppShell>,
    );

    const primaryNavigation = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(primaryNavigation).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveTextContent("Cases");
    expect(primaryNavigation.querySelector('a[href="/cases"]')).toHaveAttribute("aria-current", "page");
    expect(primaryNavigation.querySelector('a[href="/quality"]')).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Notifications" })).toHaveAttribute(
      "href",
      "/notifications",
    );
    expect(screen.getAllByText("Northstar Cloud").length).toBeGreaterThan(0);
    expect(screen.getByText("Connected simulator")).toBeInTheDocument();
  });

  it("treats mobile navigation as a dismissible modal and restores focus", async () => {
    render(
      <AppShell
        context={{
          actor: {
            id: "USR-0003",
            organizationId: "ORG-0001",
            name: "Ari Administrator",
            role: "administrator",
            permissions: ["case:read", "settings:manage"],
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
        <h1>Cases</h1>
      </AppShell>,
    );

    const opener = screen.getByRole("button", { name: "Open navigation" });
    fireEvent.click(opener);

    expect(
      screen.getByRole("dialog", { name: "Navigation menu" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Close navigation" })).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.keyDown(window, { key: "Escape" });

    await waitFor(() => expect(opener).toHaveFocus());
    expect(
      screen.queryByRole("dialog", { name: "Navigation menu" }),
    ).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
  });
});
