import {
  CASE_QUEUE_PAGE_SIZE,
  type CaseListOptions,
  type CaseQueueSort,
  type CaseQueueView,
} from "@/data/cases/case-repository";
import { getCaseRepository } from "@/data/cases/case-repository-provider";
import { CaseCategorySchema, CaseStatusSchema } from "@/domain/cases/case";
import { CaseQueue } from "@/features/cases/components/case-queue";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Cases" };

const queueViews = new Set<CaseQueueView>([
  "mine",
  "all",
  "unassigned",
  "review",
  "at_risk",
]);
const queueSorts = new Set<CaseQueueSort>(["priority", "sla", "updated"]);

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function parseOptions(
  values: Record<string, string | string[] | undefined>,
): CaseListOptions {
  const view = first(values.view);
  const sort = first(values.sort);
  const status = CaseStatusSchema.safeParse(first(values.status));
  const category = CaseCategorySchema.safeParse(first(values.category));
  const query = first(values.q)?.trim();
  return {
    query: query || undefined,
    view:
      view && queueViews.has(view as CaseQueueView)
        ? (view as CaseQueueView)
        : "all",
    status: status.success ? status.data : undefined,
    category: category.success ? category.data : undefined,
    sort:
      sort && queueSorts.has(sort as CaseQueueSort)
        ? (sort as CaseQueueSort)
        : "priority",
    cursor: first(values.cursor),
    limit: CASE_QUEUE_PAGE_SIZE,
  };
}

export default async function CasesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const repository = getCaseRepository();
  const filters = parseOptions(await searchParams);
  const page = await repository.listCases(filters);

  return (
    <CaseQueue
      page={page}
      filters={filters}
      sourceLabel="Sample workspace data"
    />
  );
}
