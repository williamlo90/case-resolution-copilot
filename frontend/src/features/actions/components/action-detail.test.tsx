import { safeFailureActionFixture, unknownOutcomeActionFixture } from "@/mocks/fixtures/action-fixtures";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ActionDetail } from "./action-detail";

describe("ActionDetail", () => {
  it("distinguishes a safe failure and allows only a controlled retry", () => {
    render(<ActionDetail detail={safeFailureActionFixture} />);
    expect(
      screen.getByRole("heading", {
        name: "No connected-system change was made",
      }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry after connection check" })).toBeVisible();
    expect(screen.getByText("Unavailable")).toBeVisible();
  });

  it("reconciles an unknown outcome without exposing retry", async () => {
    render(
      <ActionDetail
        detail={unknownOutcomeActionFixture}
        commandAction={async (_previousState, formData) => {
          expect(formData.get("command")).toBe("reconcile");
          return {
            status: "success",
            message: "Target outcome checked. No retry was attempted.",
            correlationId: "COR-TEST",
            retryAfterSeconds: null,
          };
        }}
      />,
    );
    expect(screen.getByRole("heading", { name: "Do not retry this action" })).toBeVisible();
    expect(screen.getByText("Needs attention")).toBeVisible();
    expect(screen.queryByText("degraded")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check target outcome" }));
    expect(await screen.findByRole("status")).toHaveTextContent("No retry was attempted");
  });
});
