"use client";

import { CommandStatus } from "@/components/ui/command-status";
import {
  initialCommandState,
  type ServerCommand,
} from "@/data/commands/command-state";
import type { OrganizationSettings } from "@/domain/administration/administration";
import { Save } from "lucide-react";
import { useActionState } from "react";

function BooleanSetting({
  name,
  title,
  description,
  defaultChecked,
  disabled = false,
}: {
  name: string;
  title: string;
  description: string;
  defaultChecked: boolean;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-start gap-3 text-sm text-secondary">
      <input
        name={name}
        type="checkbox"
        defaultChecked={defaultChecked}
        disabled={disabled}
        className="mt-1 size-4 accent-[#0f817c]"
      />
      <span>
        <strong className="block text-primary">{title}</strong>
        {description}
      </span>
    </label>
  );
}

export function SettingsForm({
  settings,
  updateAction,
}: {
  settings: OrganizationSettings;
  updateAction?: ServerCommand;
}) {
  const [state, formAction, pending] = useActionState(
    updateAction ??
      (async () => ({
        ...initialCommandState,
        status: "error" as const,
        message: "Sample data is read-only.",
      })),
    initialCommandState,
  );

  return (
    <form action={formAction} className="mt-7 space-y-6">
      {settings.section === "general" ? (
        <>
          <label className="grid gap-2 text-sm font-semibold text-primary">
            Organization name
            <input
              name="organization_name"
              defaultValue={settings.configuration.organizationName}
              required
              className="h-10 rounded-md border border-border px-3 font-normal"
            />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-primary">
            Locale
            <input
              name="locale"
              defaultValue={settings.configuration.locale}
              required
              pattern="[a-z]{2}(-[A-Z]{2})?"
              className="h-10 rounded-md border border-border px-3 font-normal"
            />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-primary">
            Time zone
            <input
              name="time_zone"
              defaultValue={settings.configuration.timeZone}
              required
              className="h-10 rounded-md border border-border px-3 font-normal"
            />
          </label>
        </>
      ) : null}

      {settings.section === "approvals" ? (
        <>
          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold text-primary">
              Administrator review thresholds
            </legend>
            <div className="grid gap-3 sm:grid-cols-2">
              {Object.entries(
                settings.configuration.administratorFinancialLimits,
              )
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([currency, amount]) => (
                  <label
                    key={currency}
                    className="grid gap-2 text-xs font-semibold text-primary"
                  >
                    {currency}
                    <input
                      name={`limit_${currency}`}
                      type="number"
                      min="0.01"
                      step="0.01"
                      defaultValue={amount}
                      required
                      className="h-10 rounded-md border border-border px-3 text-sm font-normal"
                    />
                  </label>
                ))}
            </div>
          </fieldset>
          <BooleanSetting
            name="require_decision_reason"
            title="Require a reason for every decision"
            description="Reviewers must explain approve, reject, change, or escalate decisions."
            defaultChecked
            disabled
          />
        </>
      ) : null}

      {settings.section === "notifications" ? (
        <>
          <BooleanSetting
            name="sla_risk_alerts"
            title="SLA risk alerts"
            description="Notify owners when a case is approaching its response limit."
            defaultChecked={settings.configuration.slaRiskAlerts}
          />
          <BooleanSetting
            name="review_waiting_alerts"
            title="Review waiting alerts"
            description="Notify supervisors when a submitted decision is waiting."
            defaultChecked={settings.configuration.reviewWaitingAlerts}
          />
          <BooleanSetting
            name="action_recovery_alerts"
            title="Action recovery alerts"
            description="Notify responsible operators when an outcome must be checked before retrying."
            defaultChecked={settings.configuration.actionRecoveryAlerts}
          />
          <BooleanSetting
            name="email_delivery"
            title="Email delivery"
            description="Create email delivery intents in addition to in-app notifications."
            defaultChecked={settings.configuration.emailDelivery}
          />
        </>
      ) : null}

      {settings.section === "security" ? (
        <>
          <BooleanSetting
            name="hide_sensitive_customer_fields"
            title="Hide sensitive customer fields"
            description="Redact contact values outside authorized workflows."
            defaultChecked={
              settings.configuration.hideSensitiveCustomerFields
            }
          />
          <label className="grid gap-2 text-sm font-semibold text-primary">
            Session duration in minutes
            <input
              name="session_duration_minutes"
              type="number"
              min="15"
              max="1440"
              defaultValue={settings.configuration.sessionDurationMinutes}
              required
              className="h-10 rounded-md border border-border px-3 font-normal"
            />
          </label>
        </>
      ) : null}

      {settings.section === "retention" ? (
        <>
          <label className="grid gap-2 text-sm font-semibold text-primary">
            Audit retention in days
            <input
              name="audit_retention_days"
              type="number"
              min="365"
              max="3650"
              defaultValue={settings.configuration.auditRetentionDays}
              required
              className="h-10 rounded-md border border-border px-3 font-normal"
            />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-primary">
            Conversation retention in days
            <input
              name="conversation_retention_days"
              type="number"
              min="30"
              max="3650"
              defaultValue={settings.configuration.conversationRetentionDays}
              required
              className="h-10 rounded-md border border-border px-3 font-normal"
            />
          </label>
          <BooleanSetting
            name="legal_hold_enabled"
            title="Allow legal hold"
            description="Preserve governed case records when a legal hold is active."
            defaultChecked={settings.configuration.legalHoldEnabled}
          />
        </>
      ) : null}

      <button
        type="submit"
        disabled={!updateAction || pending}
        className="inline-flex h-10 items-center gap-2 rounded-md bg-action px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Save aria-hidden="true" size={16} />
        {pending ? "Saving..." : "Save settings"}
      </button>
      <CommandStatus state={state} />
    </form>
  );
}
