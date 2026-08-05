import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import type { SettingsSection } from "@/domain/administration/administration";
import { SettingsPage } from "@/features/administration/components/settings-page";
import { notFound } from "next/navigation";
import { updateSettings } from "../../_actions/settings";

const sections = ["general", "approvals", "notifications", "security", "retention"] as const;
export const dynamic = "force-dynamic";

export default async function SettingsRoute({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (!sections.includes(section as SettingsSection)) notFound();
  const repository = getAdministrationRepository();
  const settings = await repository.getSettings(section as SettingsSection);
  return (
    <SettingsPage
      settings={settings}
      connected={repository.source === "api"}
      updateAction={
        repository.source === "api"
          ? updateSettings.bind(null, settings.section, settings.version)
          : undefined
      }
    />
  );
}
