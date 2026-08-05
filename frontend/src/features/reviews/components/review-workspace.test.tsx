import { reviewSnapshotFixtures } from "@/mocks/fixtures/review-fixtures";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReviewWorkspace } from "./review-workspace";

describe("ReviewWorkspace", () => {
  it("requires reservation and an attributable reason before a decision", async () => {
    const reserveAction = async () => ({
      status: "success" as const,
      message: "Review reserved.",
      correlationId: "COR-RESERVE",
      retryAfterSeconds: null,
    });
    const decideAction = async (_previousState: unknown, formData: FormData) => {
      expect(formData.get("decision")).toBe("approve");
      expect(formData.get("reason")).toBe(
        "Verified against current policy and facts.",
      );
      return {
        status: "success" as const,
        message: "Decision recorded.",
        correlationId: "COR-DECISION",
        retryAfterSeconds: null,
      };
    };
    const { rerender } = render(
      <ReviewWorkspace
        snapshot={reviewSnapshotFixtures[0]}
        reserveAction={reserveAction}
      />,
    );
    expect(screen.getByRole("heading", { name: "Authorize: Reverse duplicate charge" })).toBeVisible();
    expect(screen.getByText("Case version")).toBeVisible();
    expect(screen.getAllByText("Policy guidance")).toHaveLength(2);
    expect(screen.getAllByText("Risk checks")).toHaveLength(2);
    expect(screen.queryByText("CTX-2026-07-21.1")).not.toBeInTheDocument();
    expect(screen.queryByText("RISK-3.4")).not.toBeInTheDocument();
    expect(screen.queryByText("reverse_charge")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reserve review" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Review reserved.");

    const reservedSnapshot = structuredClone(reviewSnapshotFixtures[0]);
    reservedSnapshot.review.status = "reserved";
    reservedSnapshot.review.reservation = {
      reviewerId: "USR-0003",
      reviewerName: "Demo Administrator",
      reservedAt: "2026-07-21T03:41:00.000Z",
      expiresAt: "2026-07-21T04:11:00.000Z",
    };
    rerender(
      <ReviewWorkspace
        snapshot={reservedSnapshot}
        decideAction={decideAction}
      />,
    );
    const approve = screen.getByRole("button", { name: "Approve" });
    expect(approve).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Reason for decision" }), { target: { value: "Verified against current policy and facts." } });
    fireEvent.click(approve);
    expect(await screen.findByText("Decision recorded.")).toBeVisible();
  });

  it("hard-stops a stale or externally reserved snapshot", () => {
    render(<ReviewWorkspace snapshot={reviewSnapshotFixtures[1]} />);
    expect(screen.getByRole("heading", { name: "Decision blocked" })).toBeVisible();
    expect(screen.getByText(/Account context changed/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("preserves a terminal decision when the source case later changes", () => {
    const approvedSnapshot = structuredClone(reviewSnapshotFixtures[1]);
    approvedSnapshot.review.status = "approved";

    render(<ReviewWorkspace snapshot={approvedSnapshot} />);

    expect(screen.getByRole("heading", { name: "Review complete" })).toBeVisible();
    expect(screen.getByText(/This review is approved/)).toBeVisible();
    expect(screen.getByText(/recorded review remains unchanged/)).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Decision blocked" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });
});
