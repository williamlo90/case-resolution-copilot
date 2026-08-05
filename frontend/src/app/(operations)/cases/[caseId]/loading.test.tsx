import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CaseWorkspaceLoading from "./loading";

describe("CaseWorkspaceLoading", () => {
  it("provides immediate, accessible feedback while a case loads", () => {
    render(<CaseWorkspaceLoading />);

    expect(
      screen.getByRole("status", { name: "Opening case" }),
    ).toHaveAttribute("aria-busy", "true");
  });
});
