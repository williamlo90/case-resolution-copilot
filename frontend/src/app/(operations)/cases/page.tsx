import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { ApiClientError } from "@/data/api/api-client";
import { getCaseRepository } from "@/data/cases/case-repository-provider";
import { DataLoadFailure } from "@/components/ui/data-load-failure";
import {
  CASE_QUEUE_PAGE_SIZE,
  type CaseListOptions,
  type CaseQueueSort,
  type CaseQueueView,
} from "@/data/cases/case-repository";
import {
  CaseCategorySchema,
  CaseStatusSchema,
} from "@/domain/cases/case";
import { CaseQueue } from "@/features/cases/components/case-queue";
import type { Metadata } from "next";
import { ZodError } from "zod";
import { assignCaseToMe } from "../_actions/cases";

export const metadata: Metadata = { title: "Cases" };
export const dynamic = "force-dynamic";

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
    view: view && queueViews.has(view as CaseQueueView)
      ? (view as CaseQueueView)
      : "all",
    status: status.success ? status.data : undefined,
    category: category.success ? category.data : undefined,
    sort: sort && queueSorts.has(sort as CaseQueueSort)
      ? (sort as CaseQueueSort)
      : "priority",
    cursor: first(values.cursor),
    limit: CASE_QUEUE_PAGE_SIZE,
  };
}

export default async function CasesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const repository = getCaseRepository();
  const administrationRepository = getAdministrationRepository();
  const rawSearchParams = await searchParams;
  const options = parseOptions(rawSearchParams);
  let page;
  let session;
  try {
    [page, session] = await Promise.all([
      repository.listCases(options),
      administrationRepository.getSessionContext(),
    ]);
  } catch (error) {
    if (error instanceof ApiClientError) {
      return (
        <DataLoadFailure
          title="Cases could not be loaded"
          description="The workspace is available, but the case list could not be prepared. Try again or share the support reference with an administrator."
          retryHref="/cases"
          code={error.code}
          reference={error.correlationId}
          diagnosticPaths={error.diagnosticPaths}
        />
      );
    }
    if (error instanceof ZodError) {
      return (
        <DataLoadFailure
          title="Cases could not be loaded"
          description="Some case information was not in the expected format. No case data was changed."
          retryHref="/cases"
          code="invalid_case_data"
          diagnosticPaths={error.issues
            .slice(0, 8)
            .map((issue) => issue.path.join(".") || "$")}
        />
      );
    }
    throw error;
  }
  return (
    <CaseQueue
      page={page}
      filters={options}
      sourceLabel={repository.source === "api" ? "Connected workspace data" : "Sample workspace data"}
      assignAction={
        repository.source === "api" &&
        session.actor.permissions.includes("case:manage")
          ? assignCaseToMe
          : undefined
      }
    />
  );
}
