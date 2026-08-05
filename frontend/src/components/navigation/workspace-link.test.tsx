import { fireEvent, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({
    prefetch,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    prefetch?: boolean | null;
  }) => <a data-prefetch={String(prefetch)} {...props} />,
}));

import { WorkspaceLink } from "./workspace-link";

describe("WorkspaceLink", () => {
  it("uses client navigation without speculative protected-route loading", () => {
    render(<WorkspaceLink href="/cases/CS-2048">Open case</WorkspaceLink>);

    expect(screen.getByRole("link", { name: "Open case" })).toHaveAttribute(
      "data-prefetch",
      "false",
    );
  });

  it("prefetches only after the user shows intent", () => {
    render(<WorkspaceLink href="/cases/CS-2048">Open case</WorkspaceLink>);
    const link = screen.getByRole("link", { name: "Open case" });

    fireEvent.mouseEnter(link);

    expect(link).toHaveAttribute("data-prefetch", "null");
  });
});
