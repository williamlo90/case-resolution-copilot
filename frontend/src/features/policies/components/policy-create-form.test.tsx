import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PolicyCreateForm } from "./policy-create-form";

describe("PolicyCreateForm", () => {
  it("collects plain-language policy fields and submits a draft", async () => {
    const action = vi.fn(async () => ({
      status: "error" as const,
      message: "Test validation response.",
      correlationId: null,
      retryAfterSeconds: null,
    }));
    render(<PolicyCreateForm action={action} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Title" }), {
      target: { value: "Cancellation policy" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Summary" }), {
      target: { value: "Rules for cancellation requests." },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Source name" }), {
      target: { value: "Support handbook" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Policy text" }), {
      target: {
        value:
          "## Eligibility\nA verified cancellation request may be reviewed.",
      },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Create policy draft" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Test validation response",
    );
    expect(action).toHaveBeenCalledOnce();
  });
});
