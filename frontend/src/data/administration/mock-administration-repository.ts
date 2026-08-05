import {
  OrganizationSettingsSchema,
  SessionContextSchema,
  type OrganizationSettings,
  type SettingsSection,
} from "@/domain/administration/administration";
import {
  connectionFixtures,
  invitationFixtures,
  memberFixtures,
} from "@/mocks/fixtures/administration-fixtures";
import type { AdministrationRepository } from "./administration-repository";

const updatedAt = "2026-07-21T03:30:00.000Z";

const mockSettings: Record<SettingsSection, OrganizationSettings> = {
  general: OrganizationSettingsSchema.parse({
    id: "SET-MOCK-GENERAL",
    organizationId: "ORG-0001",
    section: "general",
    configuration: {
      organizationName: "Northstar Cloud",
      locale: "en-US",
      timeZone: "Asia/Jakarta",
    },
    version: 1,
    updatedAt,
    usingDefaults: true,
  }),
  approvals: OrganizationSettingsSchema.parse({
    id: "SET-MOCK-APPROVALS",
    organizationId: "ORG-0001",
    section: "approvals",
    configuration: {
      administratorFinancialLimits: { USD: 1000, IDR: 15000000 },
      requireDecisionReason: true,
    },
    version: 1,
    updatedAt,
    usingDefaults: true,
  }),
  notifications: OrganizationSettingsSchema.parse({
    id: "SET-MOCK-NOTIFICATIONS",
    organizationId: "ORG-0001",
    section: "notifications",
    configuration: {
      slaRiskAlerts: true,
      reviewWaitingAlerts: true,
      actionRecoveryAlerts: true,
      emailDelivery: false,
    },
    version: 1,
    updatedAt,
    usingDefaults: true,
  }),
  security: OrganizationSettingsSchema.parse({
    id: "SET-MOCK-SECURITY",
    organizationId: "ORG-0001",
    section: "security",
    configuration: {
      hideSensitiveCustomerFields: true,
      sessionDurationMinutes: 480,
    },
    version: 1,
    updatedAt,
    usingDefaults: true,
  }),
  retention: OrganizationSettingsSchema.parse({
    id: "SET-MOCK-RETENTION",
    organizationId: "ORG-0001",
    section: "retention",
    configuration: {
      auditRetentionDays: 2555,
      conversationRetentionDays: 730,
      legalHoldEnabled: true,
    },
    version: 1,
    updatedAt,
    usingDefaults: true,
  }),
};

export const mockAdministrationRepository: AdministrationRepository = {
  source: "mock",
  async getSessionContext() {
    return SessionContextSchema.parse({
      actor: {
        id: "USR-0003",
        organizationId: "ORG-0001",
        name: "Ari Administrator",
        role: "administrator",
        permissions: [
          "case:read",
          "review:read",
          "action:read",
          "policy:read",
          "quality:read",
          "connection:read",
          "connection:manage",
          "member:read",
          "member:invite",
          "member:manage",
          "policy:manage",
          "audit:read",
          "settings:manage",
        ],
        authenticationMode: "deterministic_development",
      },
      organization: {
        id: "ORG-0001",
        name: "Northstar Cloud",
        slug: "northstar-cloud",
        version: 1,
        locale: "en-US",
        timeZone: "Asia/Jakarta",
      },
    });
  },
  async listConnections() {
    return structuredClone(connectionFixtures);
  },
  async listMembers() {
    return structuredClone(memberFixtures);
  },
  async listInvitations() {
    return structuredClone(invitationFixtures);
  },
  async getSettings(section) {
    return structuredClone(mockSettings[section]);
  },
};
