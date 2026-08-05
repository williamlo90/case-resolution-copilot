import type { CaseListOptions } from "@/data/cases/case-repository";

export function queueHref(
  filters: CaseListOptions,
  changes: Partial<CaseListOptions>,
): string {
  const values = { ...filters, ...changes };
  const parameters = new URLSearchParams();
  if (values.query) parameters.set("q", values.query);
  if (values.view && values.view !== "all") parameters.set("view", values.view);
  if (values.status) parameters.set("status", values.status);
  if (values.category) parameters.set("category", values.category);
  if (values.sort && values.sort !== "priority") {
    parameters.set("sort", values.sort);
  }
  if (values.cursor) parameters.set("cursor", values.cursor);
  const query = parameters.toString();
  return query ? `/cases?${query}` : "/cases";
}
