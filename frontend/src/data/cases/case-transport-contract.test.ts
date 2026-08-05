import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

type JsonSchema = {
  required?: string[];
  $defs?: Record<string, JsonSchema>;
};

type CaseTransportContract = {
  schema_version: string;
  models: Record<string, JsonSchema>;
};

const contractPath = resolve(
  process.cwd(),
  "..",
  "contracts",
  "case-transport.schema.json",
);
const contract = JSON.parse(
  readFileSync(contractPath, "utf8"),
) as CaseTransportContract;

function requiredFields(schema: JsonSchema | undefined): string[] {
  return [...(schema?.required ?? [])].sort();
}

describe("case transport contract", () => {
  it("keeps the workspace fields consumed by the Zod adapter explicit", () => {
    const detail = contract.models.CaseDetailResponse;
    const definitions = detail?.$defs;

    expect(contract.schema_version).toBe(
      "support-copilot-case-transport-v1",
    );
    expect(requiredFields(detail)).toEqual(["data"]);
    expect(requiredFields(definitions?.CaseWorkspaceResponse)).toEqual([
      "case",
      "request",
      "conversation",
      "customer",
      "business_contexts",
      "facts",
      "missing_information",
      "evidence",
      "risks",
      "proposal",
      "response_draft",
      "proposed_actions",
      "activity",
      "collections",
      "available_commands",
    ].sort());
    expect(requiredFields(definitions?.CaseSummaryResponse)).toEqual([
      "id",
      "organization_id",
      "source_id",
      "external_reference",
      "category",
      "issue",
      "customer",
      "status",
      "owner",
      "urgency",
      "risk",
      "sla_minutes_remaining",
      "updated_at",
      "source_freshness",
      "impact",
      "version",
    ].sort());
    expect(
      requiredFields(definitions?.CaseWorkspaceCollectionsResponse),
    ).toEqual([
      "business_contexts",
      "messages",
      "activity",
    ].sort());
  });

  it("keeps queue and history page envelopes aligned", () => {
    expect(requiredFields(contract.models.CaseListResponse)).toEqual([
      "items",
      "next_cursor",
      "previous_cursor",
      "total",
      "offset",
      "limit",
      "summary_scope",
      "summary",
    ].sort());
    expect(
      requiredFields(contract.models.ConversationMessagePageResponse),
    ).toEqual(["items", "next_cursor", "total"].sort());
    expect(
      requiredFields(contract.models.CaseActivityPageResponse),
    ).toEqual([
      "items",
      "next_cursor",
      "total",
    ].sort());
  });
});
