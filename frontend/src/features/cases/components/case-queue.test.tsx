import { caseSummaryFixtures } from "@/mocks/fixtures/case-fixtures";
import type {
  CaseListOptions,
  CaseListPage,
} from "@/data/cases/case-repository";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CaseQueue } from "./case-queue";

function queuePage(
  values: Partial<CaseListPage> = {},
): CaseListPage {
  return {
    items: caseSummaryFixtures,
    nextCursor: null,
    previousCursor: null,
    total: caseSummaryFixtures.length,
    offset: 0,
    limit: 8,
    summaryScope: "organization",
    summary: {
      total: caseSummaryFixtures.length,
      attention: 1,
      review: 1,
      slaAtRisk: 1,
      unassigned: 1,
    },
    ...values,
  };
}

const filters: CaseListOptions = {
  view: "all",
  sort: "priority",
  limit: 8,
};

describe("CaseQueue", () => {
  it("presents a generic operational queue before a case is opened", () => {
    render(
      <CaseQueue
        page={queuePage()}
        filters={filters}
        sourceLabel="Sample workspace data"
      />,
    );

    expect(screen.getByRole("heading", { name: "Cases" })).toBeVisible();
    expect(screen.getByText("Needs attention")).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Risk" })).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "Owner" })).toBeVisible();
    expect(screen.getAllByRole("link", { name: "CS-2048" })[0]).toHaveAttribute("href", "/cases/CS-2048");
  });

  it("encodes views and search as server-owned queue parameters", () => {
    render(
      <CaseQueue
        page={queuePage()}
        filters={filters}
        sourceLabel="Sample workspace data"
      />,
    );

    expect(
      screen.getByRole("link", { name: "Waiting for review" }),
    ).toHaveAttribute("href", "/cases?view=review");
    const search = screen.getByRole("search");
    expect(search).toHaveAttribute("method", "get");
    expect(screen.getByRole("textbox", { name: "Search cases" })).toHaveAttribute(
      "name",
      "q",
    );
  });

  it("explains when no case source has supplied data", () => {
    render(
      <CaseQueue
        page={queuePage({
          items: [],
          total: 0,
          summary: {
            total: 0,
            attention: 0,
            review: 0,
            slaAtRisk: 0,
            unassigned: 0,
          },
        })}
        filters={filters}
        sourceLabel="Connected workspace data"
      />,
    );
    expect(screen.getByText("No cases yet")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Reset view" }),
    ).not.toBeInTheDocument();
  });

  it("keeps cases after the first hundred reachable through server cursors", () => {
    render(
      <CaseQueue
        page={queuePage({
          items: [caseSummaryFixtures[0]],
          previousCursor: "cursor-96",
          nextCursor: "cursor-112",
          total: 121,
          offset: 104,
        })}
        filters={filters}
        sourceLabel="Connected workspace data"
      />,
    );

    expect(screen.getByText("Showing 105 to 105 of 121 cases")).toBeVisible();
    expect(screen.getByRole("link", { name: "Previous page" })).toHaveAttribute(
      "href",
      "/cases?cursor=cursor-96",
    );
    expect(screen.getByRole("link", { name: "Next page" })).toHaveAttribute(
      "href",
      "/cases?cursor=cursor-112",
    );
  });

  it("assigns an unassigned case only after the command succeeds", async () => {
    render(
      <CaseQueue
        page={queuePage()}
        filters={filters}
        sourceLabel="Connected demo source"
        assignAction={async (_previousState, formData) => {
          expect(formData.get("case_id")).toBe("CS-2046");
          expect(formData.get("expected_version")).toBe("1");
          return {
            status: "success",
            message: "The case was assigned to you.",
            correlationId: null,
            retryAfterSeconds: null,
          };
        }}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /Assign to me/ })[0]);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "assigned to you",
    );
  });
});
