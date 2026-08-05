"use client";

import { usePresentationPreferences } from "@/components/providers/presentation-provider";
import { OperationsPageHeader } from "@/components/ui/operations-page-header";
import type { ServerCommand } from "@/data/commands/command-state";
import type {
  OrganizationSettings,
  SettingsSection,
} from "@/domain/administration/administration";
import { WorkspaceLink as Link } from "@/components/navigation/workspace-link";
import { formatDateTime } from "@/lib/presentation-format";
import { SettingsForm } from "./settings-form";

export const settingsSections = [
  "general",
  "approvals",
  "notifications",
  "security",
  "retention",
] as const;
export type { SettingsSection };

const names: Record<SettingsSection, string> = {
  general: "Organization",
  approvals: "Approval rules",
  notifications: "Notifications",
  security: "Security",
  retention: "Retention and redaction",
};

export function SettingsPage({
  settings,
  connected,
  updateAction,
}: {
  settings: OrganizationSettings;
  connected: boolean;
  updateAction?: ServerCommand;
}) {
  const presentation = usePresentationPreferences();
  return (
    <div className="min-h-[calc(100vh-60px)] bg-surface">
      <OperationsPageHeader
        title="Settings"
        description="Organization controls and governance defaults."
        meta={`Administrator access / ${connected ? "connected" : "sample"}`}
      />
      <div className="mx-auto grid max-w-[1540px] lg:grid-cols-[240px_minmax(0,760px)]">
        <nav
          aria-label="Settings sections"
          className="border-b border-border px-4 py-5 lg:border-b-0 lg:border-r sm:px-6"
        >
          <div className="flex gap-2 overflow-x-auto lg:grid">
            {settingsSections.map((item) => (
              <Link
                key={item}
                href={`/settings/${item}`}
                aria-current={settings.section === item ? "page" : undefined}
                className={`min-w-max rounded-md px-3 py-2 text-sm font-medium ${
                  settings.section === item
                    ? "bg-info-bg text-action"
                    : "text-secondary hover:bg-surface-subtle"
                }`}
              >
                {names[item]}
              </Link>
            ))}
          </div>
        </nav>
        <div className="px-4 py-7 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-primary">
                {names[settings.section]}
              </h2>
              <p className="mt-2 text-sm text-secondary">
                Version {settings.version}
                {settings.usingDefaults ? " / using defaults" : ""}
              </p>
            </div>
            <time
              dateTime={settings.updatedAt}
              className="text-xs text-muted"
            >
              Updated{" "}
              {formatDateTime(settings.updatedAt, presentation, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </time>
          </div>
          <SettingsForm settings={settings} updateAction={updateAction} />
        </div>
      </div>
    </div>
  );
}
