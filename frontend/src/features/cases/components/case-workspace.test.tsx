import { primaryCaseWorkspaceFixture } from "@/mocks/fixtures/case-fixtures";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CaseWorkspace } from "./case-workspace";

describe("CaseWorkspace", () => {
  it("separates facts, uncertainty, evidence, and human authority", async () => {
    render(
      <CaseWorkspace
        workspace={primaryCaseWorkspaceFixture}
        submitReviewAction={async () => ({
          status: "success",
          message: "Case submitted for review.",
          correlationId: "COR-TEST",
          retryAfterSeconds: null,
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: "Issue summary" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Verified facts" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Information needed" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Reverse duplicate charge" })).toBeVisible();
    expect(
      screen.getByText("Human review required before execution"),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "submitted for review",
    );
  });

  it("provides functional conversation, evidence, and activity tabs", async () => {
    render(
      <CaseWorkspace
        workspace={primaryCaseWorkspaceFixture}
        saveDraftAction={async () => ({
          status: "success",
          message: "Draft saved.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "Conversation" }));
    expect(await screen.findByRole("heading", { name: "Customer conversation" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Response draft" })).toBeVisible();
    expect(
      screen.getByText(
        /I was charged twice for the same monthly subscription/,
      ),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Evidence" }));
    expect(await screen.findByRole("heading", { name: "Policy guidance" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Risk checks" })).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    expect(await screen.findByRole("heading", { name: "Case activity" })).toBeVisible();
    const auditButton = screen.getByRole("button", { name: "Download audit" });
    expect(auditButton.closest("form")).toHaveAttribute(
      "action",
      "/cases/CS-2048/audit",
    );
    expect(auditButton.closest("form")).toHaveAttribute("method", "post");
  });

  it("separates information requests from later human approval", () => {
    render(
      <CaseWorkspace
        workspace={{
          ...primaryCaseWorkspaceFixture,
          proposal: {
            ...primaryCaseWorkspaceFixture.proposal!,
            state: "information_needed",
          },
          proposedActions: [
            {
              ...primaryCaseWorkspaceFixture.proposedActions[0],
              type: "request_information",
              label: "Request the missing information",
              impact: null,
              reviewRequired: false,
            },
          ],
        }}
      />,
    );

    expect(
      screen.getByText("No approval needed to request information"),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Human review applies later, before any financial or customer-impacting action can run.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByText("Supervisor review required"),
    ).not.toBeInTheDocument();
  });

  it("does not present a legacy placeholder as a customer response", async () => {
    const placeholderBody =
      "We received your request and are reviewing the available information.";
    render(
      <CaseWorkspace
        workspace={{
          ...primaryCaseWorkspaceFixture,
          proposal: null,
          responseDraft: {
            ...primaryCaseWorkspaceFixture.responseDraft!,
            source: "placeholder",
            editVersion: 1,
            body: placeholderBody,
            status: "draft",
          },
        }}
        saveDraftAction={async () => ({
          status: "success",
          message: "Draft saved.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
      />,
    );

    expect(screen.queryByText(placeholderBody)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Conversation" }));
    expect(
      await screen.findByRole("textbox", { name: "Response draft" }),
    ).toHaveValue("");
  });

  it("collects checked records with fields that match the selected record type", async () => {
    const addEvidence = vi.fn(async () => ({
      status: "success" as const,
      message: "Checked record added.",
      correlationId: null,
      retryAfterSeconds: null,
    }));
    render(
      <CaseWorkspace
        workspace={primaryCaseWorkspaceFixture}
        addEvidenceAction={addEvidence}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Evidence" }));
    expect(
      await screen.findByRole("heading", { name: "Add a checked record" }),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Record name"), {
      target: { value: "Second settled charge" },
    });
    fireEvent.change(screen.getByLabelText("Where you checked it"), {
      target: { value: "Billing system" },
    });
    fireEvent.change(screen.getByLabelText("Record reference"), {
      target: { value: "PAY-SECOND" },
    });
    fireEvent.change(screen.getByLabelText("Current status"), {
      target: { value: "settled" },
    });
    fireEvent.change(screen.getByLabelText("Amount (required)"), {
      target: { value: "49.00" },
    });
    fireEvent.change(screen.getByLabelText("Currency (required)"), {
      target: { value: "USD" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add checked record" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Checked record added",
    );
    expect(addEvidence).toHaveBeenCalledOnce();

    fireEvent.change(screen.getByLabelText("Record type"), {
      target: { value: "account" },
    });
    expect(screen.getByLabelText("Identity check")).toBeVisible();
    expect(screen.queryByLabelText("Amount (required)")).not.toBeInTheDocument();
  });

  it("supports arrow-key navigation for workspace and composer tabs", async () => {
    render(
      <CaseWorkspace
        workspace={primaryCaseWorkspaceFixture}
        addNoteAction={async () => ({
          status: "success",
          message: "The internal note was added.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
      />,
    );

    const briefTab = screen.getByRole("tab", { name: "Decision brief" });
    briefTab.focus();
    fireEvent.keyDown(briefTab, { key: "ArrowRight" });

    const conversationTab = screen.getByRole("tab", { name: "Conversation" });
    expect(conversationTab).toHaveFocus();
    expect(conversationTab).toHaveAttribute("aria-selected", "true");
    const conversationPanel = await screen.findByRole("tabpanel", {
      name: "Conversation",
    });
    expect(conversationPanel).toHaveAttribute(
      "aria-labelledby",
      conversationTab.id,
    );

    const replyTab = screen.getByRole("tab", { name: "Reply" });
    replyTab.focus();
    fireEvent.keyDown(replyTab, { key: "ArrowRight" });
    const noteTab = screen.getByRole("tab", { name: "Internal note" });
    expect(noteTab).toHaveFocus();
    expect(noteTab).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("tabpanel", { name: "Internal note" }),
    ).toBeVisible();
  });

  it("loads older conversation and activity pages without replacing current items", async () => {
    const loadConversation = vi.fn(async () => ({
      status: "success" as const,
      items: [
        {
          ...primaryCaseWorkspaceFixture.conversation.messages[0],
          id: "MSG-OLDER",
          body: "Earlier customer context.",
          createdAt: "2026-07-20T02:46:00.000Z",
        },
      ],
      nextCursor: null,
      total: 2,
    }));
    const loadActivity = vi.fn(async () => ({
      status: "success" as const,
      items: [
        {
          ...primaryCaseWorkspaceFixture.activity[0],
          id: "EV-OLDER",
          label: "Earlier case event",
          timestamp: "2026-07-20T02:46:00.000Z",
        },
      ],
      nextCursor: null,
      total: 5,
    }));
    render(
      <CaseWorkspace
        workspace={{
          ...primaryCaseWorkspaceFixture,
          collections: {
            ...primaryCaseWorkspaceFixture.collections,
            messages: {
              returned: 1,
              total: 2,
              hasMore: true,
              nextCursor: "conversation-cursor",
            },
            activity: {
              returned: 4,
              total: 5,
              hasMore: true,
              nextCursor: "activity-cursor",
            },
          },
        }}
        loadConversationHistoryAction={loadConversation}
        loadActivityHistoryAction={loadActivity}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Conversation" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Load earlier messages" }),
    );
    expect(await screen.findByText("Earlier customer context.")).toBeVisible();
    expect(
      screen.getByText(/I was charged twice for the same monthly subscription/),
    ).toBeVisible();
    expect(loadConversation).toHaveBeenCalledWith("conversation-cursor");

    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Load earlier activity" }),
    );
    expect(await screen.findByText("Earlier case event")).toBeVisible();
    expect(screen.getByText("Ready for supervisor review")).toBeVisible();
    expect(loadActivity).toHaveBeenCalledWith("activity-cursor");
  });

  it("records replies and internal notes as separate conversation entries", async () => {
    render(
      <CaseWorkspace
        workspace={primaryCaseWorkspaceFixture}
        addReplyAction={async () => ({
          status: "success",
          message: "The reply was added to the case conversation.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
        addNoteAction={async () => ({
          status: "success",
          message: "The internal note was added.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Conversation" }));
    expect(
      await screen.findByRole("button", { name: "Add reply" }),
    ).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Add reply" }));
    expect(
      await screen.findByText("The reply was added to the case conversation."),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("tab", { name: "Internal note" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Internal note" }), {
      target: { value: "Customer identity was verified by phone." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add internal note" }));
    expect(await screen.findByText("The internal note was added.")).toBeVisible();
  });

  it("does not show write controls to a read-only case viewer", async () => {
    render(<CaseWorkspace workspace={primaryCaseWorkspaceFixture} />);

    fireEvent.click(screen.getByRole("tab", { name: "Conversation" }));
    expect(
      await screen.findByText(/your role cannot add replies/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("textbox", { name: "Response draft" }),
    ).not.toBeInTheDocument();
  });

  it("uses plain language for case progress controls", async () => {
    render(
      <CaseWorkspace
        workspace={primaryCaseWorkspaceFixture}
        workflowActions={[
          {
            mode: "request_information",
            action: async () => ({
              status: "success",
              message: "The case is now waiting for more information.",
              correlationId: null,
              retryAfterSeconds: null,
            }),
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Ask for information" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "waiting for more information",
    );
  });

  it("lets an operator start work on a new case", async () => {
    render(
      <CaseWorkspace
        workspace={{
          ...primaryCaseWorkspaceFixture,
          case: { ...primaryCaseWorkspaceFixture.case, status: "new" },
        }}
        workflowActions={[
          {
            mode: "start_investigation",
            action: async () => ({
              status: "success",
              message: "The case is now under investigation.",
              correlationId: null,
              retryAfterSeconds: null,
            }),
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Start investigation" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "now under investigation",
    );
  });

  it("hides audit export when the actor is not allowed to export it", async () => {
    render(
      <CaseWorkspace
        workspace={{
          ...primaryCaseWorkspaceFixture,
          availableCommands:
            primaryCaseWorkspaceFixture.availableCommands.filter(
              (command) => command !== "export_audit",
            ),
        }}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Activity" }));
    expect(await screen.findByRole("heading", { name: "Case activity" })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Download audit" })).not.toBeInTheDocument();
  });

  it("lets an operator refresh the decision brief without changing approval controls", async () => {
    render(
      <CaseWorkspace
        workspace={primaryCaseWorkspaceFixture}
        prepareBriefAction={async () => ({
          status: "success",
          message:
            "Decision brief updated. AI drafted the wording; checks and approval rules stayed unchanged.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
      />,
    );

    expect(screen.getByText("AI-assisted wording")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Refresh brief" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Decision brief updated",
    );
    expect(screen.getByRole("button", { name: "Submit for review" })).toBeDisabled();
  });

  it("uses a clear prepare label when no decision brief exists", () => {
    render(
      <CaseWorkspace
        workspace={{ ...primaryCaseWorkspaceFixture, proposal: null }}
        prepareBriefAction={async () => ({
          status: "success",
          message: "Decision brief updated.",
          correlationId: null,
          retryAfterSeconds: null,
        })}
      />,
    );

    expect(screen.getByRole("button", { name: "Prepare brief" })).toBeVisible();
  });
});
