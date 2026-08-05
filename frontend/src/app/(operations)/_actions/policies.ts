"use server";

import { ApiClientError, apiRequest } from "@/data/api/api-client";
import type { CommandState } from "@/data/commands/command-state";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";
import { commandFailure, commandSuccess } from "./shared";

const policyCommandEnvelopeSchema = z.object({
  data: z.object({
    policy: z.object({
      id: z.string().min(1),
    }),
  }),
});

function policyApplicability(formData: FormData) {
  const decisionScope = String(formData.get("decision_scope") ?? "").trim();
  const caseCategories = formData
    .getAll("case_categories")
    .map(String)
    .filter(Boolean);
  if (!decisionScope || !caseCategories.length) {
    throw new ApiClientError(
      "Choose a decision type and at least one case category.",
      422,
      "policy_applicability_required",
      "unavailable",
    );
  }
  return {
    decision_scope: decisionScope,
    case_categories: caseCategories,
    products: ["all"],
    regions: ["all"],
    channels: ["all"],
    customer_tiers: ["all"],
  };
}

function optionalPolicyDate(
  formData: FormData,
  field: string,
  options: { required?: boolean } = {},
): string | null {
  const { required = false } = options;
  const value = String(formData.get(field) ?? "").trim();
  if (!value && !required) return null;
  const date = new Date(`${value}T00:00:00.000Z`);
  if (!value || Number.isNaN(date.valueOf())) {
    throw new ApiClientError(
      "Choose a valid effective date.",
      422,
      "policy_effective_date_invalid",
      "unavailable",
    );
  }
  return date.toISOString();
}

function policyDraftBody(formData: FormData, expectedPolicyVersion: number) {
  const sourceText = String(formData.get("source_text") ?? "").trim();
  if (sourceText.length < 20) {
    throw new ApiClientError(
      "Policy text must contain at least 20 characters.",
      422,
      "policy_source_text_required",
      "unavailable",
    );
  }
  return {
    expected_policy_version: expectedPolicyVersion,
    source_text: sourceText,
    applicability: policyApplicability(formData),
    effective_from: optionalPolicyDate(formData, "effective_from"),
    effective_to: optionalPolicyDate(formData, "effective_to"),
  };
}

export async function createPolicy(
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  const title = String(formData.get("title") ?? "").trim();
  const description = String(formData.get("description") ?? "").trim();
  const sourceName = String(formData.get("source_name") ?? "").trim();
  const sourceText = String(formData.get("source_text") ?? "").trim();
  if (!title || !description || !sourceName || sourceText.length < 20) {
    return commandFailure(
      new ApiClientError(
        "Add a title, summary, source name, and policy text of at least 20 characters.",
        422,
        "policy_input_required",
        "unavailable",
      ),
    );
  }

  let policyId: string;
  try {
    const response = await apiRequest(
      "/api/policies",
      policyCommandEnvelopeSchema,
      {
        method: "POST",
        body: {
          title,
          description,
          source: { kind: "manual", name: sourceName },
          source_text: sourceText,
          applicability: policyApplicability(formData),
          effective_from: optionalPolicyDate(formData, "effective_from"),
          effective_to: optionalPolicyDate(formData, "effective_to"),
        },
      },
    );
    policyId = response.data.policy.id;
    revalidatePath("/policies");
  } catch (error) {
    return commandFailure(error);
  }
  redirect(`/policies/${encodeURIComponent(policyId)}`);
}

export async function runPolicyLifecycleCommand(
  policyId: string,
  expectedPolicyVersion: number,
  versionNumber: number,
  expectedVersion: number,
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  void _previousState;
  const command = String(formData.get("command") ?? "");
  let path: string;
  let body: Record<string, unknown>;
  let message: string;

  try {
    if (command === "create_draft") {
      path = `/api/policies/${encodeURIComponent(policyId)}/versions`;
      body = policyDraftBody(formData, expectedPolicyVersion);
      message = "A new editable policy version was created.";
    } else if (command === "retry_source") {
      path = `/api/policies/${encodeURIComponent(policyId)}/retry-source`;
      body = policyDraftBody(formData, expectedPolicyVersion);
      message = "The policy source was checked again.";
    } else if (command === "submit_review") {
      path = `/api/policies/${encodeURIComponent(policyId)}/versions/${versionNumber}/submit-review`;
      body = {
        expected_policy_version: expectedPolicyVersion,
        expected_version: expectedVersion,
      };
      message = "The policy was submitted for review.";
    } else if (command === "publish") {
      path = `/api/policies/${encodeURIComponent(policyId)}/versions/${versionNumber}/publish`;
      body = {
        expected_policy_version: expectedPolicyVersion,
        expected_version: expectedVersion,
        effective_from: optionalPolicyDate(formData, "effective_from"),
      };
      message = "The policy version was published.";
    } else if (command === "schedule") {
      path = `/api/policies/${encodeURIComponent(policyId)}/versions/${versionNumber}/schedule`;
      body = {
        expected_policy_version: expectedPolicyVersion,
        expected_version: expectedVersion,
        effective_from: optionalPolicyDate(formData, "effective_from", {
          required: true,
        }),
      };
      message = "The policy version was scheduled.";
    } else if (command === "retire") {
      path = `/api/policies/${encodeURIComponent(policyId)}/versions/${versionNumber}/retire`;
      body = {
        expected_policy_version: expectedPolicyVersion,
        expected_version: expectedVersion,
      };
      message = "The policy version was retired.";
    } else {
      throw new ApiClientError(
        "Choose an available policy action.",
        422,
        "policy_command_required",
        "unavailable",
      );
    }

    await apiRequest(path, policyCommandEnvelopeSchema, {
      method: "POST",
      body,
    });
    revalidatePath(`/policies/${policyId}`);
    revalidatePath("/policies");
    return commandSuccess(message);
  } catch (error) {
    return commandFailure(error);
  }
}
