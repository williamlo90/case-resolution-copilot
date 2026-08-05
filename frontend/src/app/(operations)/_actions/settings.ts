"use server";

import { ApiClientError, apiRequest } from "@/data/api/api-client";
import type { CommandState } from "@/data/commands/command-state";
import { revalidatePath } from "next/cache";
import {
  commandEnvelopeSchema,
  commandFailure,
  commandSuccess,
} from "./shared";

export async function updateSettings(
  section: string,
  expectedVersion: number,
  _previousState: CommandState,
  formData: FormData,
): Promise<CommandState> {
  let configuration: Record<string, unknown>;
  if (section === "general") {
    configuration = {
      organization_name: String(formData.get("organization_name") ?? "").trim(),
      locale: String(formData.get("locale") ?? "").trim(),
      time_zone: String(formData.get("time_zone") ?? "").trim(),
    };
  } else if (section === "approvals") {
    configuration = {
      administrator_financial_limits: Object.fromEntries(
        [...formData.entries()]
          .filter(([key]) => key.startsWith("limit_"))
          .map(([key, value]) => [key.slice(6), Number(value)]),
      ),
      require_decision_reason: true,
    };
  } else if (section === "notifications") {
    configuration = {
      sla_risk_alerts: formData.get("sla_risk_alerts") === "on",
      review_waiting_alerts: formData.get("review_waiting_alerts") === "on",
      action_recovery_alerts:
        formData.get("action_recovery_alerts") === "on",
      email_delivery: formData.get("email_delivery") === "on",
    };
  } else if (section === "security") {
    configuration = {
      hide_sensitive_customer_fields:
        formData.get("hide_sensitive_customer_fields") === "on",
      session_duration_minutes: Number(
        formData.get("session_duration_minutes"),
      ),
    };
  } else if (section === "retention") {
    configuration = {
      audit_retention_days: Number(formData.get("audit_retention_days")),
      conversation_retention_days: Number(
        formData.get("conversation_retention_days"),
      ),
      legal_hold_enabled: formData.get("legal_hold_enabled") === "on",
    };
  } else {
    return commandFailure(
      new ApiClientError(
        "The settings section is not supported.",
        422,
        "settings_section_invalid",
        "unavailable",
      ),
    );
  }

  try {
    await apiRequest(
      `/api/settings/${encodeURIComponent(section)}`,
      commandEnvelopeSchema,
      {
        method: "PUT",
        body: {
          section,
          expected_version: expectedVersion,
          configuration,
        },
      },
    );
    revalidatePath(`/settings/${section}`);
    return commandSuccess("The settings were saved.");
  } catch (error) {
    return commandFailure(error);
  }
}
