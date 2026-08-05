import { ConnectionsPage } from "@/features/administration/components/connections-page";
import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import type { Metadata } from "next";
import { testConnection } from "../_actions/connections";

export const metadata: Metadata = { title: "Connections" };
export const dynamic = "force-dynamic";

export default async function ConnectionsRoute() {
  const repository = getAdministrationRepository();
  const context = await repository.getSessionContext();
  const canManage = context.actor.permissions.includes("connection:manage");
  return (
    <ConnectionsPage
      connections={await repository.listConnections()}
      connected={repository.source === "api"}
      testConnectionAction={
        repository.source === "api" && canManage ? testConnection : undefined
      }
    />
  );
}
