import type { CaseSummary, CaseWorkspace } from "@/domain/cases/case";

export const CASE_QUEUE_PAGE_SIZE = 8;

export type CaseQueueView =
  | "mine"
  | "all"
  | "unassigned"
  | "review"
  | "at_risk";

export type CaseQueueSort = "priority" | "sla" | "updated";

export type CaseListOptions = {
  query?: string;
  view?: CaseQueueView;
  status?: CaseSummary["status"];
  category?: CaseSummary["category"];
  sort?: CaseQueueSort;
  cursor?: string;
  limit?: number;
};

export type CaseQueueSummary = {
  total: number;
  attention: number;
  review: number;
  slaAtRisk: number;
  unassigned: number;
};

export type CaseListPage = {
  items: readonly CaseSummary[];
  nextCursor: string | null;
  previousCursor: string | null;
  total: number;
  offset: number;
  limit: number;
  summaryScope: "organization";
  summary: CaseQueueSummary;
};

export interface CaseRepository {
  readonly source: "api" | "mock";
  listCases(options?: CaseListOptions): Promise<CaseListPage>;
  getCaseWorkspace(caseId: string): Promise<CaseWorkspace | null>;
}
