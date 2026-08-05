import { connectionFixtures, invitationFixtures, memberFixtures, onboardingStepFixtures } from "@/mocks/fixtures/administration-fixtures";
import { describe, expect, it } from "vitest";
import { ConnectionSchema, InvitationSchema, MemberSchema, OnboardingStepSchema } from "./administration";

describe("administration contract", () => {
  it("contains capability and health metadata without secret values", () => {
    expect(ConnectionSchema.array().parse(connectionFixtures)).toHaveLength(4);
    expect(JSON.stringify(connectionFixtures)).not.toMatch(/password|apiKey|secretValue/i);
  });
  it("models roles, authority, and resumable onboarding", () => {
    expect(MemberSchema.array().parse(memberFixtures)).toHaveLength(4);
    expect(InvitationSchema.array().parse(invitationFixtures)[0].status).toBe(
      "pending",
    );
    expect(OnboardingStepSchema.array().parse(onboardingStepFixtures).some((item) => item.status === "current")).toBe(true);
  });
});
