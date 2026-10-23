import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResolutionPanel } from "./resolution-panel";
import { ActionOutcome } from "./action-outcome";
import { resolutionHeading } from "./presentation";
import type { Resolution } from "./contract";
import { readyActionFixture } from "@/mocks/fixtures/action-fixtures";
import { initialCommandState } from "@/data/commands/command-state";

const base: Resolution = {
  case_id: "CS-2048", version: 4, status: "in_progress",
  closure: {eligible: false, blocker: "Every action needs a current verified outcome.", verification_ids: []},
  available_commands: [], actions: [{id:"AC-7001",status:"completed"}], events: [],
};
const proof = {external_reference:"REFUND-01", effect_count:1, impact_amount:"240", impact_currency:"USD", observed_at:"2026-10-23T10:00:00Z"};
const event = {id:"verification-1",kind:"action_verified",at:proof.observed_at,actor_id:"reviewer",previous_event_id:null,data:{action_id:"AC-7001",proof}};
const verified: Resolution = {...base,closure:{eligible:true,blocker:null,verification_ids:[event.id]},available_commands:["completed"],events:[event]};

describe("Resolution controls", () => {
  it("does not allow closure on a receipt alone", () => {
    render(<ResolutionPanel data={base} commandAction={vi.fn()} />);
    expect(screen.queryByRole("button",{name:"Close case"})).not.toBeInTheDocument();
    expect(screen.getByRole("heading",{name:"Outcome not checked yet"})).toBeVisible();
    expect(screen.getByRole("link",{name:/View action and verification/})).toHaveAttribute("href","/actions/AC-7001");
  });
  it("requires reason and communication reference, keeping the same key on retry", async () => {
    const payloads: FormData[] = [];
    const action = vi.fn(async (_state: typeof initialCommandState, form: FormData) => {
      payloads.push(form);
      return {...initialCommandState,status:"error" as const,message:"Connection interrupted. Retry the saved command."};
    });
    render(<ResolutionPanel data={verified} commandAction={action} simulated />);
    const button = screen.getByRole("button",{name:"Close case"});
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason"),{target:{value:"Refund verified and customer informed."}});
    fireEvent.change(screen.getByLabelText("Simulated customer communication reference"),{target:{value:"SIM-MESSAGE-01"}});
    fireEvent.click(button);
    await waitFor(()=>expect(action).toHaveBeenCalledTimes(1));
    await waitFor(()=>expect(button).not.toBeDisabled());
    fireEvent.click(button);
    await waitFor(()=>expect(action).toHaveBeenCalledTimes(2));
    expect(payloads[0].get("kind")).toBe("completed");
    expect(payloads[0].get("reference")).toBe("SIM-MESSAGE-01");
    expect(payloads[0].get("command_id")).toBe(payloads[1].get("command_id"));
    expect(screen.getByText("USD 240.00")).toBeVisible();
  });
  it("clears closure fields when the case becomes eligible for reopen", () => {
    const action = vi.fn();
    const {rerender} = render(<ResolutionPanel data={verified} commandAction={action} simulated />);
    fireEvent.change(screen.getByLabelText("Reason"),{target:{value:"Previous closure reason"}});
    rerender(<ResolutionPanel data={{...verified,version:5,status:"completed",available_commands:["reopened"]}} commandAction={action} simulated />);
    expect(screen.getByLabelText("Reason")).toHaveValue("");
    expect(screen.getByLabelText("New evidence reference")).toHaveValue("");
    expect(screen.getByRole("button",{name:"Reopen case"})).toBeDisabled();
    expect(screen.queryByRole("button",{name:"Close case"})).not.toBeInTheDocument();
  });
  it("does not equate historical verification with current closure eligibility", () => {
    expect(resolutionHeading({...verified,closure:{...base.closure}})).toBe("Outcome needs a fresh check");
  });
});

describe("Action result guidance", () => {
  it("requires a matching verification event, not completed status alone", () => {
    render(<ActionOutcome detail={{...readyActionFixture,action:{...readyActionFixture.action,status:"completed"}}} resolution={base}/>);
    expect(screen.getByRole("heading",{name:"Outcome not checked yet"})).toBeVisible();
  });
  it("shows the recorded amount and one effect after readback", () => {
    render(<ActionOutcome detail={{...readyActionFixture,action:{...readyActionFixture.action,status:"completed"}}} resolution={verified} synthetic/>);
    expect(screen.getByText("USD 240.00")).toBeVisible();
    expect(screen.getByText(/No real money moved/)).toBeVisible();
    expect(screen.getByRole("link",{name:"Review evidence and close case"})).toHaveAttribute("href","/cases/CS-2048?tab=resolution");
  });
  it("warns about a duplicate refund after timeout", () => {
    render(<ActionOutcome detail={{...readyActionFixture,action:{...readyActionFixture.action,status:"outcome_unknown"}}} resolution={base}/>);
    expect(screen.getByRole("heading",{name:"Outcome uncertain"})).toBeVisible();
    expect(screen.getByText(/Check target outcome below/)).toBeVisible();
  });
  it.each(["stale_proposal", "expired_approval"] as const)("explains %s before another execution", blocker => {
    render(<ActionOutcome detail={{...readyActionFixture,executionBlocker:blocker}} resolution={base}/>);
    expect(screen.getByRole("heading",{name:"Approval needs a new review"})).toBeVisible();
    expect(screen.getByText(/previous approval cannot authorize/)).toBeVisible();
  });
});
