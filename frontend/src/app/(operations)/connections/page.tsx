import { getAdministrationRepository } from "@/data/administration/administration-repository-provider";
import { ApiClientError } from "@/data/api/api-client";
import { apiConnectedInboxRepository } from "@/data/connections/api-connected-inbox-repository";
import type { InboxConnectionStatus } from "@/domain/connections/connected-inbox";
import {
  selectConnectedInbox,
  withoutInboxConnections,
} from "@/domain/connections/connected-inbox";
import { ConnectionsPage } from "@/features/administration/components/connections-page";
import { ConnectedInboxPanel } from "@/features/connections/components/connected-inbox-panel";
import type { Metadata } from "next";
import { testConnection } from "../_actions/connections";
import {
  disconnectInbox,
  pauseInbox,
  resumeInbox,
  syncInbox,
} from "../_actions/inbox-controls";
import {
  importInboxThread,
  listInboxThreads,
} from "../_actions/inbox-import";
import { startInboxOAuth } from "../_actions/inbox-authorization";

export const metadata: Metadata = { title: "Connections" };
export const dynamic = "force-dynamic";

export default async function ConnectionsRoute() {
  const repository = getAdministrationRepository();
  const context = await repository.getSessionContext();
  const connections = await repository.listConnections();
  const inbox = selectConnectedInbox(connections);
  const canManage = context.actor.permissions.includes("connection:manage");
  const canRead = context.actor.permissions.includes("connection:read");
  const canImport =
    canRead && context.actor.permissions.includes("case:manage");
  const connected = repository.source === "api";
  const inboxId = inbox?.id;
  let inboxStatus: InboxConnectionStatus | null = null;
  let statusLoadError: string | null = null;
  if (connected && inboxId) {
    try {
      inboxStatus = await apiConnectedInboxRepository.getStatus(inboxId);
    } catch (error) {
      if (!(error instanceof ApiClientError)) throw error;
      statusLoadError =
        "Live inbox status could not be loaded. Existing connection details may be out of date.";
    }
  }
  return (
    <ConnectionsPage
      connections={withoutInboxConnections(connections)}
      connected={connected}
      testConnectionAction={
        connected && canManage ? testConnection : undefined
      }
      featuredContent={
        <ConnectedInboxPanel
          inbox={inbox}
          inboxStatus={inboxStatus}
          statusLoadError={statusLoadError}
          connectedWorkspace={connected}
          startAuthorizationAction={
            connected && canManage ? startInboxOAuth : undefined
          }
          listThreadsAction={
            connected && inboxId && canRead
              ? listInboxThreads.bind(null, inboxId)
              : undefined
          }
          importThreadAction={
            connected && inboxId && canImport
              ? importInboxThread.bind(null, inboxId)
              : undefined
          }
          syncAction={
            connected && inboxId && canManage
              ? syncInbox.bind(null, inboxId)
              : undefined
          }
          pauseAction={
            connected && inboxId && canManage
              ? pauseInbox.bind(null, inboxId)
              : undefined
          }
          resumeAction={
            connected && inboxId && canManage
              ? resumeInbox.bind(null, inboxId)
              : undefined
          }
          disconnectAction={
            connected && inboxId && canManage
              ? disconnectInbox.bind(null, inboxId)
              : undefined
          }
        />
      }
    />
  );
}
