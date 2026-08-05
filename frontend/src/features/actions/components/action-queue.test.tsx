import { actionSummaryFixtures } from "@/mocks/fixtures/action-fixtures";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ActionQueue } from "./action-queue";

describe("ActionQueue", () => {
  it("shows approved changes and recovery work", () => {
    render(<ActionQueue actions={actionSummaryFixtures} sourceLabel="Sample action data" />);
    expect(screen.getByRole("heading", { name: "Actions" })).toBeVisible();
    expect(screen.getAllByText("Failed safely").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Outcome unknown").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "AC-7001" })).toHaveAttribute("href", "/actions/AC-7001");
    expect(screen.queryByText("reverse_charge")).not.toBeInTheDocument();
  });

  it("filters by execution state", () => {
    render(<ActionQueue actions={actionSummaryFixtures} sourceLabel="Sample action data" />);
    fireEvent.change(screen.getByRole("combobox", { name: "Filter action status" }), { target: { value: "outcome_unknown" } });
    expect(screen.getByText("Issue delivery compensation")).toBeVisible();
    expect(screen.queryByText("Reverse duplicate charge")).not.toBeInTheDocument();
    expect(screen.queryByText("issue_compensation")).not.toBeInTheDocument();
  });

  it("explains an empty workspace without implying filters hid actions", () => {
    render(<ActionQueue actions={[]} sourceLabel="Connected action records" />);
    expect(screen.getByText("No approved actions yet")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Reset filters" })).not.toBeInTheDocument();
  });

  it("offers a reset only when filters hide existing actions", () => {
    render(<ActionQueue actions={actionSummaryFixtures} sourceLabel="Sample action data" />);
    fireEvent.change(screen.getByRole("textbox", { name: "Search actions" }), {
      target: { value: "does-not-exist" },
    });
    expect(screen.getByText("No actions match this view")).toBeVisible();
    expect(screen.getByRole("button", { name: "Reset filters" })).toBeVisible();
  });

  it("shows why a ready action cannot currently run", () => {
    render(
      <ActionQueue
        actions={[
          {
            ...actionSummaryFixtures[0],
            executionBlocker: "connection_unavailable",
          },
        ]}
        sourceLabel="Connected action records"
      />,
    );

    expect(screen.getByRole("link", { name: "AC-7001" })).toBeVisible();
    expect(screen.getByText("Connection unavailable")).toBeVisible();
  });
});
