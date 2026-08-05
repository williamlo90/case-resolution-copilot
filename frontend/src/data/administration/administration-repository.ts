import type {
  Connection,
  Invitation,
  Member,
  OrganizationSettings,
  SessionContext,
  SettingsSection,
} from "@/domain/administration/administration";

export interface AdministrationRepository {
  readonly source: "api" | "mock";
  getSessionContext(): Promise<SessionContext>;
  listConnections(): Promise<readonly Connection[]>;
  listMembers(): Promise<readonly Member[]>;
  listInvitations(): Promise<readonly Invitation[]>;
  getSettings(section: SettingsSection): Promise<OrganizationSettings>;
}
