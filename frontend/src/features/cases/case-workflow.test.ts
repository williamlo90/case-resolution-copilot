import { describe, expect, it } from "vitest";
import { caseWorkflowModes, caseWorkflowTarget } from "./case-workflow";

describe("case workflow controls", () => {
  it("keeps both valid next steps visible for a new case", () => {
    expect(
      caseWorkflowModes([
        "request_information",
        "add_evidence",
        "start_investigation",
      ]),
    ).toEqual(["start_investigation", "request_information"]);
  });

  it("maps workflow controls to the expected case status", () => {
    expect(caseWorkflowTarget("start_investigation")).toBe("investigating");
    expect(caseWorkflowTarget("resume_investigation")).toBe("investigating");
    expect(caseWorkflowTarget("request_information")).toBe(
      "information_needed",
    );
  });
});
