import { publishedPolicyFixture } from "@/mocks/fixtures/policy-fixtures";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PolicyDetail } from "./policy-detail";

describe("PolicyDetail", () => {
  it("exposes governed draft and retirement actions when connected", () => {
    render(
      <PolicyDetail
        detail={publishedPolicyFixture}
        lifecycleAction={async () => ({
          status: "success",
          message: "A new editable policy version was created.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
      />,
    );
    expect(screen.getByText("Immutable record")).toBeVisible();
    fireEvent.click(screen.getByText("Create editable version"));
    expect(
      screen.getByRole("button", { name: "Create draft version" }),
    ).toBeVisible();
    expect(screen.getByText("Retire this policy")).toBeVisible();
    expect(screen.getByText("Current v3")).toBeVisible();
  });

  it("shows immutable historical usage by version", () => {
    render(<PolicyDetail detail={publishedPolicyFixture} />);
    expect(screen.getByRole("heading", { name: "Cases that used this version" })).toBeVisible();
    expect(screen.getByRole("link", { name: "CS-2048" })).toBeVisible();
  });
});
