import {
  initialInboxControlState,
  type InboxControlAction,
} from "@/features/connections/action-contracts";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InboxConnectionControls } from "./inbox-connection-controls";

describe("InboxConnectionControls", () => {
  it("keeps a successful pause after resume fails, then reflects a successful retry and disconnect", async () => {
    const pauseAction: InboxControlAction = async () => ({
      ...initialInboxControlState,
      status: "success",
      message: "Inbox updates paused.",
      connectionState: "paused",
    });
    const resumeAction = vi
      .fn<InboxControlAction>()
      .mockResolvedValueOnce({
        ...initialInboxControlState,
        status: "error",
        message: "Inbox authorization was rejected.",
        connectionState: "unchanged",
      })
      .mockResolvedValueOnce({
        ...initialInboxControlState,
        status: "success",
        message: "Inbox updates resumed.",
        connectionState: "ready",
      });
    const disconnectAction: InboxControlAction = async () => ({
      ...initialInboxControlState,
      status: "success",
      message: "Inbox disconnected.",
      connectionState: "disconnected",
    });
    render(
      <InboxConnectionControls
        pauseAction={pauseAction}
        resumeAction={resumeAction}
        disconnectAction={disconnectAction}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Pause updates" }));
    expect(await screen.findByText("Paused", { exact: true })).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Resume updates" }));
    expect(await screen.findByText("Inbox authorization was rejected.")).toBeVisible();
    expect(screen.getByText("Paused", { exact: true })).toBeVisible();
    expect(screen.getByRole("button", { name: "Resume updates" })).toBeEnabled();
    expect(screen.queryByText("Active", { exact: true })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resume updates" }));
    expect(await screen.findByText("Inbox updates resumed.")).toBeVisible();
    expect(screen.getByText("Active", { exact: true })).toBeVisible();
    expect(screen.getByRole("button", { name: "Pause updates" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(await screen.findByText("Inbox disconnected.")).toBeVisible();
    expect(screen.getByText("Disconnected", { exact: true })).toBeVisible();
    expect(screen.getByRole("button", { name: "Update now" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeDisabled();
  });

  it("retains an initially paused inbox when an update leaves its state unchanged", async () => {
    const syncAction: InboxControlAction = async () => ({
      ...initialInboxControlState,
      status: "success",
      message: "Inbox is up to date.",
      connectionState: "unchanged",
    });
    render(<InboxConnectionControls initiallyPaused syncAction={syncAction} />);

    fireEvent.click(screen.getByRole("button", { name: "Update now" }));
    expect(await screen.findByText("Inbox is up to date.")).toBeVisible();
    expect(screen.getByText("Paused", { exact: true })).toBeVisible();
    expect(screen.queryByText("Active", { exact: true })).not.toBeInTheDocument();
  });
});
