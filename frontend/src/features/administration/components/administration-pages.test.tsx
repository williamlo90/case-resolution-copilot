import {
  connectionFixtures,
  invitationFixtures,
  memberFixtures,
} from "@/mocks/fixtures/administration-fixtures";
import { mockAdministrationRepository } from "@/data/administration/mock-administration-repository";
import type { CommandState } from "@/data/commands/command-state";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectionsPage } from "./connections-page";
import { SettingsPage } from "./settings-page";
import { TeamPage } from "./team-page";

describe("administration pages", () => {
  it("explains the next step when no connections are registered", () => {
    render(<ConnectionsPage connections={[]} connected />);

    expect(
      screen.getByRole("heading", { name: "No connections registered" }),
    ).toBeVisible();
    expect(
      screen.getByText(/Add a support case source or controlled action tool/),
    ).toBeVisible();
  });

  it("inspects connection capabilities and returns a backend command result", async () => {
    const testConnection = async (
      _connectionId: string,
      _version: number,
      _state: CommandState,
      _formData: FormData,
    ): Promise<CommandState> => {
      void _connectionId;
      void _version;
      void _state;
      void _formData;
      return {
        status: "success",
        message: "The connection health check completed.",
        correlationId: null,
        retryAfterSeconds: null,
      };
    };
    const connectionsWithApiTerms = [
      {
        ...connectionFixtures[0],
        capabilities: {
          ...connectionFixtures[0].capabilities,
          read: ["lookup_transaction"],
        },
      },
      ...connectionFixtures.slice(1),
    ];
    render(
      <ConnectionsPage
        connections={connectionsWithApiTerms}
        connected
        testConnectionAction={testConnection}
      />,
    );
    const opener = screen.getAllByRole("button", { name: "View details" })[0];
    fireEvent.click(opener);
    expect(screen.getByRole("dialog", { name: "Billing system connection details" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Close connection details" })).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");
    expect(screen.getByText("View transactions")).toBeVisible();
    expect(screen.queryByText("lookup_transaction")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "health check completed",
      ),
    );
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(opener).toHaveFocus());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
  });
  it("shows team authority and governed settings from repository data", async () => {
    const { unmount } = render(
      <TeamPage members={memberFixtures} connected={false} />,
    );
    expect(
      screen.getByText("Review decisions and run approved actions"),
    ).toBeVisible();
    expect(screen.queryByText(/action:execute/)).not.toBeInTheDocument();
    unmount();
    const settings =
      await mockAdministrationRepository.getSettings("approvals");
    render(
      <SettingsPage
        settings={settings}
        connected={false}
      />,
    );
    expect(screen.getByText("Administrator review thresholds")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save settings" })).toBeDisabled();
  });

  it("shows pending invitations only with permitted controls", async () => {
    const revokeInvitation = async (
      _invitationId: string,
      _version: number,
      _state: CommandState,
      _formData: FormData,
    ): Promise<CommandState> => {
      void _invitationId;
      void _version;
      void _state;
      void _formData;
      return {
        status: "success",
        message: "The invitation was revoked.",
        correlationId: null,
        retryAfterSeconds: null,
      };
    };
    render(
      <TeamPage
        members={memberFixtures}
        invitations={invitationFixtures}
        connected
        revokeInvitationAction={revokeInvitation}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Invitations" }),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Invite member" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "invitation was revoked",
    );
  });
});
