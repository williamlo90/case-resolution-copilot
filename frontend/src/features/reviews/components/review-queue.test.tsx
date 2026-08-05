import { reviewSummaryFixtures } from "@/mocks/fixtures/review-fixtures";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReviewQueue } from "./review-queue";

describe("ReviewQueue", () => {
  it("shows an authorization queue rather than a copy of the case queue", () => {
    render(<ReviewQueue reviews={reviewSummaryFixtures} sourceLabel="Sample review data" />);
    expect(screen.getByRole("heading", { name: "Reviews" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Recommended resolution" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Why review" })).toBeVisible();
    expect(screen.getByRole("link", { name: "RV-5001" })).toHaveAttribute("href", "/reviews/RV-5001");
    expect(screen.queryByRole("columnheader", { name: "Owner" })).not.toBeInTheDocument();
  });

  it("supports review-specific search and policy filtering", () => {
    render(<ReviewQueue reviews={reviewSummaryFixtures} sourceLabel="Sample review data" />);
    fireEvent.change(screen.getByRole("combobox", { name: "Filter policy state" }), { target: { value: "possible_conflict" } });
    expect(screen.getByText("Prepare service exception resolution")).toBeVisible();
    expect(screen.queryByText("Reverse duplicate charge")).not.toBeInTheDocument();
  });

  it("distinguishes an empty review queue from filtered results", () => {
    render(<ReviewQueue reviews={[]} sourceLabel="Connected review records" />);
    expect(screen.getByText("No reviews yet")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Reset filters" })).not.toBeInTheDocument();
  });

  it("offers a reset when search hides existing reviews", () => {
    render(<ReviewQueue reviews={reviewSummaryFixtures} sourceLabel="Sample review data" />);
    fireEvent.change(screen.getByRole("textbox", { name: "Search reviews" }), {
      target: { value: "does-not-exist" },
    });
    expect(screen.getByText("No reviews match these filters")).toBeVisible();
    expect(screen.getByRole("button", { name: "Reset filters" })).toBeVisible();
  });
});
