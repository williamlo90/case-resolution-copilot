import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppNavigation, type AppPermission } from "./app-navigation";

describe("AppNavigation", () => {
  const identity = {
    organizationName: "Northstar Cloud",
    workspaceMode: "Demo",
    actorName: "Ari Administrator",
    actorRole: "administrator",
  };

  it("shows only modules permitted for the active actor", () => {
    const permissions = new Set<AppPermission>(["cases:view"]);
    render(
      <AppNavigation
        pathname="/cases"
        permissions={permissions}
        {...identity}
      />,
    );

    expect(screen.getByRole("link", { name: "Cases" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByText("Reviews")).not.toBeInTheDocument();
    expect(screen.queryByText("Team")).not.toBeInTheDocument();
  });

  it("renders completed modules as permission-filtered links", () => {
    const permissions = new Set<AppPermission>(["cases:view", "actions:view"]);
    render(
      <AppNavigation
        pathname="/cases"
        permissions={permissions}
        {...identity}
      />,
    );

    expect(screen.getByRole("link", { name: "Actions" })).toHaveAttribute("href", "/actions");
  });
});
