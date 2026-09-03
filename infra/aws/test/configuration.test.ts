import { App } from "aws-cdk-lib";
import { describe, expect, it } from "vitest";

import { readConfiguration } from "../lib/configuration";

function appWith(overrides: Record<string, string> = {}): App {
  return new App({
    context: {
      projectName: "case-resolution-copilot",
      stage: "portfolio",
      frontendOrigin: "https://example.vercel.app",
      cloudFrontPrefixListId: "pl-31a34658",
      includeRuntime: "false",
      imageDigest: `sha256:${"0".repeat(64)}`,
      sourceRevision: "a".repeat(40),
      logRetentionDays: "7",
      autoDestroyAt: "2099-01-01T00:00:00Z",
      ...overrides,
    },
  });
}

describe("readConfiguration", () => {
  it(
    "returns bounded portfolio defaults",
    () => {
      expect(readConfiguration(appWith())).toEqual({
        projectName: "case-resolution-copilot",
        stage: "portfolio",
        frontendOrigin: "https://example.vercel.app",
        cloudFrontPrefixListId: "pl-31a34658",
        includeRuntime: false,
        imageDigest: `sha256:${"0".repeat(64)}`,
        sourceRevision: "a".repeat(40),
        logRetentionDays: 7,
        autoDestroyAt: "2099-01-01T00:00:00Z",
      });
    },
    15_000,
  );

  it("rejects an insecure frontend origin", () => {
    expect(() =>
      readConfiguration(appWith({ frontendOrigin: "http://example.com" })),
    ).toThrow(/HTTPS origin/);
  });

  it("rejects an invalid image digest for runtime deployment", () => {
    expect(() =>
      readConfiguration(appWith({ includeRuntime: "true", imageDigest: "latest" })),
    ).toThrow(/sha256 container digest/);
  });

  it("requires a full source revision for runtime deployment", () => {
    expect(() =>
      readConfiguration(
        appWith({ includeRuntime: "true", sourceRevision: "abc1234" }),
      ),
    ).toThrow(/full 40-character Git commit SHA/);
  });

  it("requires a precise UTC auto-destroy time", () => {
    expect(() =>
      readConfiguration(appWith({ autoDestroyAt: "tomorrow" })),
    ).toThrow(/UTC timestamp/);
  });
});
