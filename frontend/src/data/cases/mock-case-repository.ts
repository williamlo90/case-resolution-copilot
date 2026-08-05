import { caseSummaryFixtures, caseWorkspaceFixtures } from "@/mocks/fixtures/case-fixtures";
import {
  CASE_QUEUE_PAGE_SIZE,
  type CaseListOptions,
  type CaseQueueSort,
  type CaseRepository,
} from "./case-repository";

const riskWeight = { high: 0, medium: 1, low: 2 } as const;

function mockOffset(cursor: string | undefined): number {
  if (!cursor) return 0;
  const match = /^mock-(\d+)$/.exec(cursor);
  return match ? Number(match[1]) : 0;
}

function sortedCases(
  options: CaseListOptions,
): typeof caseSummaryFixtures {
  const query = options.query?.trim().toLocaleLowerCase();
  const rows = caseSummaryFixtures.filter((item) => {
    const matchesQuery =
      !query ||
      [item.id, item.issue, item.customer.name, item.externalReference]
        .join(" ")
        .toLocaleLowerCase()
        .includes(query);
    const matchesView =
      !options.view ||
      options.view === "all" ||
      (options.view === "unassigned" && !item.owner) ||
      (options.view === "review" && item.status === "needs_review") ||
      (options.view === "at_risk" &&
        (item.risk === "high" || item.slaMinutesRemaining < 30));
    return (
      matchesQuery &&
      matchesView &&
      (!options.status || item.status === options.status) &&
      (!options.category || item.category === options.category)
    );
  });
  const sort: CaseQueueSort = options.sort ?? "priority";
  return [...rows].sort((left, right) => {
    if (sort === "sla") {
      return left.slaMinutesRemaining - right.slaMinutesRemaining;
    }
    if (sort === "updated") {
      return (right.updatedAt ?? "").localeCompare(left.updatedAt ?? "");
    }
    return (
      riskWeight[left.risk] - riskWeight[right.risk] ||
      left.slaMinutesRemaining - right.slaMinutesRemaining
    );
  });
}

export const mockCaseRepository: CaseRepository = {
  source: "mock",
  async listCases(options = {}) {
    const rows = sortedCases(options);
    const limit = options.limit ?? CASE_QUEUE_PAGE_SIZE;
    const offset = mockOffset(options.cursor);
    const items = rows.slice(offset, offset + limit);
    return structuredClone({
      items,
      nextCursor:
        offset + items.length < rows.length
          ? `mock-${offset + items.length}`
          : null,
      previousCursor:
        offset > 0 ? `mock-${Math.max(0, offset - limit)}` : null,
      total: rows.length,
      offset,
      limit,
      summaryScope: "organization",
      summary: {
        total: caseSummaryFixtures.length,
        attention: caseSummaryFixtures.filter((item) => item.risk === "high")
          .length,
        review: caseSummaryFixtures.filter(
          (item) => item.status === "needs_review",
        ).length,
        slaAtRisk: caseSummaryFixtures.filter(
          (item) => item.slaMinutesRemaining < 30,
        ).length,
        unassigned: caseSummaryFixtures.filter((item) => !item.owner).length,
      },
    });
  },
  async getCaseWorkspace(caseId) {
    const workspace = caseWorkspaceFixtures.find((candidate) => candidate.case.id === caseId);
    return workspace ? structuredClone(workspace) : null;
  },
};
