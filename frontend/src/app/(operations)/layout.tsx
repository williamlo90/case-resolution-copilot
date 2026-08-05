import { AppShell } from "@/components/layout/app-shell";
import { providerAuthenticationEnabled } from "@/config/authentication";
import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { ApiClientError } from "@/data/api/api-client";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

export const dynamic = "force-dynamic";

export default async function OperationsLayout({
  children,
}: {
  children: ReactNode;
}) {
  const providerAuthentication = providerAuthenticationEnabled();
  let context;
  try {
    context = await getAdministrationRepository().getSessionContext();
  } catch (error) {
    if (providerAuthentication && error instanceof ApiClientError) {
      if (error.status === 401) {
        redirect("/sign-in");
      }
      if (error.code === "workspace_access_denied") {
        redirect("/access-denied");
      }
      if (error.code === "workspace_selection_required") {
        redirect("/workspace-selection");
      }
    }
    throw error;
  }
  return (
    <AppShell
      context={context}
      providerAuthentication={providerAuthentication}
    >
      {children}
    </AppShell>
  );
}
