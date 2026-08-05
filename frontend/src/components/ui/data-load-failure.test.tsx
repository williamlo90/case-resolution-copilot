import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataLoadFailure } from "./data-load-failure";

describe("DataLoadFailure", () => {
  it("shows a plain-language recovery path and safe support metadata", () => {
    const { container } = render(
      <DataLoadFailure
        title="Cases could not be loaded"
        description="The case list is temporarily unavailable."
        retryHref="/cases"
        code="invalid_backend_response"
        reference="corr-test"
        diagnosticPaths={["items.0.owner.initials"]}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Cases could not be loaded" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Try again" })).toHaveAttribute(
      "href",
      "/cases",
    );
    expect(screen.getByText("Support reference: corr-test")).toBeInTheDocument();
    expect(
      container.querySelector("[data-load-error-code]"),
    ).toHaveAttribute("data-load-error-code", "invalid_backend_response");
    expect(
      container.querySelector("[data-load-error-paths]"),
    ).toHaveAttribute(
      "data-load-error-paths",
      "items.0.owner.initials",
    );
  });
});
