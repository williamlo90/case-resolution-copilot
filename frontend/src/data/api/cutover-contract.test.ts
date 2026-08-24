import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { configuredDataSource } from "./data-mode";

const activeFiles = [
  "src/app/(operations)/cases/page.tsx",
  "src/app/(operations)/cases/[caseId]/page.tsx",
  "src/app/(operations)/reviews/page.tsx",
  "src/app/(operations)/actions/page.tsx",
  "src/app/(operations)/policies/page.tsx",
  "src/app/(operations)/quality/page.tsx",
  "src/app/(operations)/connections/page.tsx",
  "src/app/(operations)/team/page.tsx",
  "src/app/(operations)/settings/[section]/page.tsx",
];

afterEach(() => {
  delete process.env.SUPPORT_COPILOT_DATA_MODE;
});

describe("frontend generic cutover", () => {
  it("uses the generic API by default and keeps mock mode explicit", () => {
    delete process.env.SUPPORT_COPILOT_DATA_MODE;
    expect(configuredDataSource()).toBe("api");
    process.env.SUPPORT_COPILOT_DATA_MODE = "mock";
    expect(configuredDataSource()).toBe("mock");
  });

  it("keeps active operational routes free of fixture and legacy task repositories", () => {
    for (const relativePath of activeFiles) {
      const source = readFileSync(join(process.cwd(), relativePath), "utf8");
      expect(source).not.toContain("@/mocks/");
      expect(source).not.toContain("getTaskRepository");
      expect(source).not.toContain("apiTaskRepository");
    }
  });

  it("submits reviews against an exact generic proposal version", () => {
    const source = readFileSync(
      join(process.cwd(), "src/app/(operations)/_actions/cases.ts"),
      "utf8",
    );
    expect(source).toContain("/proposals/${proposalVersion}/reviews");
    expect(source).not.toContain(
      "/api/cases/${encodeURIComponent(caseId)}/reviews",
    );
  });

  it("memoizes provider token resolution during one server render", () => {
    const source = readFileSync(
      join(process.cwd(), "src/data/api/api-client.ts"),
      "utf8",
    );

    expect(source).toContain('import { cache } from "react"');
    expect(source).toContain("cache(async () =>");
  });

  it("starts case queue data and session work concurrently", () => {
    const source = readFileSync(
      join(process.cwd(), "src/app/(operations)/cases/page.tsx"),
      "utf8",
    );

    expect(source).toContain("await Promise.all([");
    expect(source).toContain("repository.listCases(options)");
    expect(source).toContain("administrationRepository.getSessionContext()");
  });

  it("runs server rendering next to the Singapore backend and database", () => {
    const configuration = JSON.parse(
      readFileSync(join(process.cwd(), "vercel.json"), "utf8"),
    ) as {
      $schema?: string;
      regions?: string[];
    };

    expect(configuration.$schema).toBe("https://openapi.vercel.sh/vercel.json");
    expect(configuration.regions).toEqual(["sin1"]);
  });

  it("keeps connected-inbox draft commands behind case management permission", () => {
    const source = readFileSync(
      join(process.cwd(), "src/app/(operations)/cases/[caseId]/page.tsx"),
      "utf8",
    );

    expect(source).toContain('permissions.includes("case:manage")');
    expect(source).toContain(
      "connected && canManageCase && inboxCase && savedResponseDraft",
    );
    expect(source).toContain(
      "initialDraftDelivery={canManageCase ? latestDraftDelivery : null}",
    );
  });

  it("preserves an unresolved Gmail draft outcome when a status request fails", () => {
    const source = readFileSync(
      join(process.cwd(), "src/app/(operations)/_actions/inbox-drafts.ts"),
      "utf8",
    );

    expect(source).toContain("delivery: _previousState.delivery");
    expect(source).not.toContain("delivery: null");
  });
});
