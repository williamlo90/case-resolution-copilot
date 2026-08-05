import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OnboardingPage } from "./onboarding-page";
import { SignInPage } from "./sign-in-page";

describe("access and onboarding", () => {
  it("provides a vendor-neutral sign-in shell", () => {
    render(<SignInPage />);
    expect(screen.getByText("Case Resolution")).toBeVisible();
    expect(screen.getByText("Copilot")).toBeVisible();
    fireEvent.change(screen.getByRole("textbox", { name: "Work email" }), { target: { value: "alex@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("status")).toHaveTextContent("alex@example.com");
  });
  it("shows backend-derived readiness without a fake activation control", () => {
    render(
      <OnboardingPage
        steps={[
          {
            id: "workspace",
            label: "Workspace details",
            description: "Confirm workspace settings.",
            status: "complete",
          },
          {
            id: "policy",
            label: "Published policy",
            description: "Publish one policy.",
            status: "current",
          },
        ]}
        summary={{
          organizationName: "Northstar Cloud",
          caseCount: 3,
          publishedPolicyCount: 0,
          activeMemberCount: 2,
          connectedToolCount: 1,
        }}
      />,
    );
    expect(screen.getByText("1 of 2 complete")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Published policy");
    expect(screen.getByRole("link", { name: "Review policies" })).toHaveAttribute(
      "href",
      "/policies",
    );
    expect(
      screen.queryByRole("button", { name: "Activate demo data" }),
    ).not.toBeInTheDocument();
  });
});
