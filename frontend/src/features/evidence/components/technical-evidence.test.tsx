import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TechnicalEvidence } from "./technical-evidence";

describe("TechnicalEvidence", () => {
  it("keeps only the two essential reliability views", () => {
    render(<TechnicalEvidence activeView="evaluations"/>);
    const nav = screen.getByRole("navigation", { name: "Reliability sections" });
    expect(nav.querySelectorAll("a")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Case Checks" })).toHaveAttribute("aria-current", "page");
    const summary = screen.getByLabelText("Reliability summary");
    expect(summary).toHaveTextContent("Total8");
    expect(summary).toHaveTextContent("Passed7");
    expect(summary).toHaveTextContent("Failed1");
    expect(screen.getByText("Committed baseline")).toBeInTheDocument();
    expect(screen.getAllByText("Block and review").length).toBeGreaterThan(1);
    expect(screen.getAllByText("Approve resolution").length).toBeGreaterThan(1);
    expect(screen.getByText("The credit may exist while the case remains unresolved.")).toBeInTheDocument();
    expect(screen.getByText("No retry was attempted; the case remains in reconciliation.")).toBeInTheDocument();
    expect(screen.queryByText("Case study overview")).not.toBeInTheDocument();
    expect(screen.queryByText("STATUS = UNCERTAIN")).not.toBeInTheDocument();
  });

  it("renders safeguards and limitations separately", () => {
    render(<TechnicalEvidence activeView="architecture"/>);
    expect(screen.getByRole("heading", { name: "How It Is Checked" })).toBeInTheDocument();
    expect(screen.getByText(/Covered by frontend schemas and backend contract checks/)).toBeInTheDocument();
    expect(screen.getByText(/External case-source contract evidence has not been recorded/)).toBeInTheDocument();
  });
});
