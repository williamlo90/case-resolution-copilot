"use client";

import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { OperationsPageHeader } from "@/components/ui/operations-page-header";
import type {
  CaseListOptions,
  CaseListPage,
  CaseQueueView,
} from "@/data/cases/case-repository";
import type { ServerCommand } from "@/data/commands/command-state";
import {
  caseCategoryLabels,
  caseStatusPresentation,
} from "@/features/cases/case-presentation";
import { ArrowDownUp, Filter, Search, X } from "lucide-react";
import { useState } from "react";
import { queueHref } from "./case-queue-navigation";
import { CaseQueueSummary } from "./case-queue-summary";
import { CaseQueueTable } from "./case-queue-table";

type CaseQueueProps = {
  page: CaseListPage;
  filters: CaseListOptions;
  sourceLabel: string;
  title?: string;
  description?: string;
  assignAction?: ServerCommand;
};

const views: readonly { id: CaseQueueView; label: string }[] = [
  { id: "mine", label: "My cases" },
  { id: "all", label: "All open" },
  { id: "unassigned", label: "Unassigned" },
  { id: "review", label: "Waiting for review" },
  { id: "at_risk", label: "At risk" },
];

function QueueContextFields({
  filters,
  include,
}: {
  filters: CaseListOptions;
  include: readonly ("query" | "view" | "status" | "category" | "sort")[];
}) {
  return (
    <>
      {include.includes("query") && filters.query ? (
        <input type="hidden" name="q" value={filters.query} />
      ) : null}
      {include.includes("view") && filters.view && filters.view !== "all" ? (
        <input type="hidden" name="view" value={filters.view} />
      ) : null}
      {include.includes("status") && filters.status ? (
        <input type="hidden" name="status" value={filters.status} />
      ) : null}
      {include.includes("category") && filters.category ? (
        <input type="hidden" name="category" value={filters.category} />
      ) : null}
      {include.includes("sort") && filters.sort && filters.sort !== "priority" ? (
        <input type="hidden" name="sort" value={filters.sort} />
      ) : null}
    </>
  );
}

export function CaseQueue({
  page,
  filters,
  sourceLabel,
  title = "Cases",
  description = "Prioritize cases that need investigation or a decision.",
  assignAction,
}: CaseQueueProps) {
  const [filtersOpen, setFiltersOpen] = useState(
    Boolean(filters.status || filters.category),
  );
  const activeView = filters.view ?? "all";
  const activeSort = filters.sort ?? "priority";
  const activeFilterCount =
    Number(Boolean(filters.status)) + Number(Boolean(filters.category));

  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <OperationsPageHeader
        title={title}
        description={description}
        meta={sourceLabel}
      />

      <CaseQueueSummary summary={page.summary} />

      <div className="mx-auto max-w-[1540px] px-4 pb-8 sm:px-6 lg:px-7">
        <nav
          aria-label="Case views"
          className="overflow-x-auto border-b border-border"
        >
          <div className="flex min-w-max gap-7">
            {views.map((item) => (
              <Link
                key={item.id}
                href={queueHref(filters, {
                  view: item.id,
                  cursor: undefined,
                })}
                aria-current={activeView === item.id ? "page" : undefined}
                className={`relative inline-flex h-14 items-center text-sm font-medium transition-colors ${
                  activeView === item.id
                    ? "text-primary"
                    : "text-secondary hover:text-primary"
                }`}
              >
                {item.label}
                {activeView === item.id ? (
                  <span className="absolute inset-x-0 bottom-0 h-0.5 bg-action" />
                ) : null}
              </Link>
            ))}
          </div>
        </nav>

        <div className="py-5">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
            <form
              action="/cases"
              method="get"
              role="search"
              className="flex min-w-0 flex-1 xl:max-w-[650px]"
            >
              <QueueContextFields
                filters={filters}
                include={["view", "status", "category", "sort"]}
              />
              <label className="relative min-w-0 flex-1">
                <span className="sr-only">Search cases</span>
                <input
                  name="q"
                  defaultValue={filters.query}
                  placeholder="Search cases, customers, or IDs"
                  className="h-10 w-full rounded-l-md border border-r-0 border-border bg-surface px-3 text-sm outline-none placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/15"
                />
              </label>
              <button
                type="submit"
                aria-label="Search"
                title="Search"
                className="grid size-10 place-items-center rounded-r-md border border-border bg-surface text-secondary hover:bg-surface-subtle hover:text-primary"
              >
                <Search aria-hidden="true" size={17} />
              </button>
              {filters.query ? (
                <Link
                  href={queueHref(filters, {
                    query: undefined,
                    cursor: undefined,
                  })}
                  aria-label="Clear search"
                  title="Clear search"
                  className="ml-2 grid size-10 place-items-center text-secondary hover:text-primary"
                >
                  <X aria-hidden="true" size={17} />
                </Link>
              ) : null}
            </form>

            <div className="flex flex-wrap items-center gap-2 xl:ml-auto">
              <button
                type="button"
                onClick={() => setFiltersOpen((value) => !value)}
                aria-expanded={filtersOpen}
                className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm font-medium text-primary hover:bg-surface-subtle"
              >
                <Filter aria-hidden="true" size={16} />
                Filters
                {activeFilterCount ? (
                  <span className="grid size-5 place-items-center rounded-full bg-action text-[11px] font-semibold text-white">
                    {activeFilterCount}
                  </span>
                ) : null}
              </button>
              <form action="/cases" method="get">
                <QueueContextFields
                  filters={filters}
                  include={["query", "view", "status", "category"]}
                />
                <label className="relative block">
                  <span className="sr-only">Sort cases</span>
                  <ArrowDownUp
                    aria-hidden="true"
                    size={15}
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-secondary"
                  />
                  <select
                    name="sort"
                    value={activeSort}
                    onChange={(event) => event.currentTarget.form?.requestSubmit()}
                    className="h-10 appearance-none rounded-md border border-border bg-surface pl-9 pr-8 text-sm font-medium text-primary outline-none hover:bg-surface-subtle focus:border-focus"
                  >
                    <option value="priority">Priority</option>
                    <option value="sla">SLA</option>
                    <option value="updated">Updated</option>
                  </select>
                </label>
              </form>
            </div>
          </div>

          {filtersOpen ? (
            <form
              action="/cases"
              method="get"
              className="mt-3 flex flex-wrap items-end gap-3 border-y border-border bg-canvas/55 px-3 py-3"
            >
              <QueueContextFields
                filters={filters}
                include={["query", "view", "sort"]}
              />
              <label className="grid gap-1 text-xs font-medium text-secondary">
                Status
                <select
                  name="status"
                  defaultValue={filters.status ?? ""}
                  className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-primary"
                >
                  <option value="">All statuses</option>
                  {Object.entries(caseStatusPresentation).map(
                    ([value, item]) => (
                      <option key={value} value={value}>
                        {item.label}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label className="grid gap-1 text-xs font-medium text-secondary">
                Category
                <select
                  name="category"
                  defaultValue={filters.category ?? ""}
                  className="h-9 rounded-md border border-border bg-surface px-3 text-sm text-primary"
                >
                  <option value="">All categories</option>
                  {Object.entries(caseCategoryLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="submit"
                className="h-9 rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary/90"
              >
                Apply
              </button>
              {activeFilterCount ? (
                <Link
                  href={queueHref(filters, {
                    status: undefined,
                    category: undefined,
                    cursor: undefined,
                  })}
                  className="inline-flex h-9 items-center gap-1.5 px-2 text-sm font-medium text-secondary hover:text-primary"
                >
                  <X aria-hidden="true" size={15} />
                  Clear filters
                </Link>
              ) : null}
            </form>
          ) : null}
        </div>

        <CaseQueueTable
          page={page}
          filters={filters}
          assignAction={assignAction}
        />
      </div>
    </div>
  );
}
