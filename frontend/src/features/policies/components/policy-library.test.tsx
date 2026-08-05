import { policySummaryFixtures } from "@/mocks/fixtures/policy-fixtures";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PolicyLibrary } from "./policy-library";

describe("PolicyLibrary", () => {
  it("shows policy lifecycle, applicability, ownership, and health", () => {
    render(<PolicyLibrary policies={policySummaryFixtures} sourceLabel="Sample policy data" canManage />);
    expect(screen.getByRole("heading", { name: "Policies" })).toBeVisible();
    expect(screen.getByRole("link", { name: "New policy" })).toHaveAttribute(
      "href",
      "/policies/new",
    );
    expect(screen.getByRole("link", { name: "Billing adjustments" })).toHaveAttribute("href", "/policies/POL-1008");
    expect(screen.getByRole("columnheader", { name: "Applies to" })).toBeVisible();
    expect(screen.getAllByText("Source needs attention").length).toBeGreaterThan(0);
  });

  it("filters lifecycle states", () => {
    render(<PolicyLibrary policies={policySummaryFixtures} sourceLabel="Sample policy data" />);
    fireEvent.change(screen.getByRole("combobox", { name: "Filter policy status" }), { target: { value: "conflicting" } });
    expect(screen.getByText("Priority account exceptions")).toBeVisible();
    expect(screen.queryByText("Billing adjustments")).not.toBeInTheDocument();
  });

  it("uses setup guidance when the workspace has no policies", () => {
    render(<PolicyLibrary policies={[]} sourceLabel="Connected policy records" />);
    expect(screen.getByText("No policies yet")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Reset filters" })).not.toBeInTheDocument();
  });

  it("offers a reset when search hides existing policies", () => {
    render(<PolicyLibrary policies={policySummaryFixtures} sourceLabel="Sample policy data" />);
    fireEvent.change(screen.getByRole("textbox", { name: "Search policies" }), {
      target: { value: "does-not-exist" },
    });
    expect(screen.getByText("No policies match this view")).toBeVisible();
    expect(screen.getByRole("button", { name: "Reset filters" })).toBeVisible();
  });
});
