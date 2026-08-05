import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell, type ShellContext } from "./app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/cases",
}));

const context: ShellContext = {
  organizationName: "Northstar Cloud",
  actorName: "Ari Specialist",
  actorRole: "specialist",
  locale: "en-US",
  timeZone: "UTC",
  permissions: ["cases:view"],
};

describe("AppShell", () => {
  it("provides one main landmark and a skip link", () => {
    render(<AppShell context={context}>Case content</AppShell>);

    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getAllByRole("link", { name: "Cases" })).not.toHaveLength(0);
    expect(screen.queryByRole("link", { name: "Reviews" })).not.toBeInTheDocument();
  });

  it("opens and closes an accessible mobile navigation dialog", () => {
    render(<AppShell context={context}>Case content</AppShell>);

    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByRole("dialog", { name: "Navigation menu" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close navigation" }));
    expect(screen.queryByRole("dialog", { name: "Navigation menu" })).not.toBeInTheDocument();
  });
});
