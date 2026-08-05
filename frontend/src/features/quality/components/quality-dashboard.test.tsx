import { render, screen } from "@testing-library/react";
import { mockQualityRepository } from "@/data/quality/mock-quality-repository";
import { describe, expect, it } from "vitest";
import { QualityDashboard } from "./quality-dashboard";

describe("QualityDashboard", () => {
  it("leads with decision and operational quality evidence", async () => {
    const dashboard = await mockQualityRepository.getDashboard();
    render(<QualityDashboard dashboard={dashboard} />);
    expect(screen.getByRole("heading", { name: "Quality" })).toBeVisible();
    expect(screen.getByText("Unsafe actions blocked")).toBeVisible();
    expect(
      screen.getByRole("table", {
        name: "Attributable decision quality evidence",
      }),
    ).toBeVisible();
  });
});
