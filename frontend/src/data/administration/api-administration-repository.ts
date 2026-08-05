import { apiRequest } from "@/data/api/api-client";
import {
  ConnectionSchema,
  InvitationSchema,
  MemberSchema,
  OrganizationSettingsSchema,
  SessionContextSchema,
  type Connection,
  type Invitation,
  type Member,
  type OrganizationSettings,
  type SettingsSection,
} from "@/domain/administration/administration";
import { cache } from "react";
import { z } from "zod";
import type { AdministrationRepository } from "./administration-repository";

const organizationDataSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  slug: z.string().min(1),
  version: z.number().int().positive(),
});

const sessionOrganizationDataSchema = organizationDataSchema.extend({
  locale: z.string().min(1),
  time_zone: z.string().min(1),
});

const sessionEnvelopeSchema = z.object({
  data: z.object({
    id: z.string().min(1),
    organization_id: z.string().min(1),
    name: z.string().min(1),
    role: z
      .enum(["specialist", "supervisor", "administrator", "auditor"])
      .nullable(),
    permissions: z.array(z.string().min(1)),
    authentication_mode: z.enum(["deterministic_development", "provider"]),
    organization: sessionOrganizationDataSchema.nullable().optional(),
  }),
});

const organizationEnvelopeSchema = z.object({
  data: organizationDataSchema,
});

const apiConnectionSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  provider_type: z.string().min(1),
  environment: z.enum(["demo", "sandbox", "production"]),
  health: z.enum(["healthy", "degraded", "unavailable", "not_configured"]),
  last_checked_at: z.string().datetime().nullable(),
  credential_status: z.enum(["demo", "connected", "missing", "expired"]),
  capabilities: z.object({
    read: z.array(z.string()),
    write: z.array(z.string()),
  }),
  affected_work: z.array(z.string()),
  version: z.number().int().positive(),
});

const connectionListEnvelopeSchema = z.object({
  items: z.array(apiConnectionSchema),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
});

const apiMemberSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  email: z.string().email(),
  role: z.enum(["specialist", "supervisor", "administrator", "auditor"]),
  status: z.enum(["active", "invited", "deactivated"]),
  authority: z.array(z.string()),
  version: z.number().int().positive(),
  last_active_at: z.string().datetime().nullable(),
});

const memberListEnvelopeSchema = z.object({
  items: z.array(apiMemberSchema),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
});

const apiInvitationSchema = z.object({
  id: z.string().min(1),
  organization_id: z.string().min(1),
  email: z.string().email(),
  role: z.enum(["specialist", "supervisor", "administrator", "auditor"]),
  status: z.enum(["pending", "accepted", "expired", "revoked"]),
  version: z.number().int().positive(),
  invited_by: z.string().min(1),
  expires_at: z.string().datetime(),
  accepted_at: z.string().datetime().nullable(),
});

const invitationListEnvelopeSchema = z.object({
  items: z.array(apiInvitationSchema),
  next_cursor: z.string().nullable(),
  total: z.number().int().nonnegative(),
});

const settingsBaseSchema = {
  id: z.string().min(1),
  organization_id: z.string().min(1),
  version: z.number().int().positive(),
  updated_at: z.string().datetime(),
  using_defaults: z.boolean(),
};

const settingsEnvelopeSchema = z.object({
  data: z.discriminatedUnion("section", [
    z.object({
      ...settingsBaseSchema,
      section: z.literal("general"),
      configuration: z.object({
        organization_name: z.string().min(1),
        locale: z.string().min(1),
        time_zone: z.string().min(1),
      }),
    }),
    z.object({
      ...settingsBaseSchema,
      section: z.literal("approvals"),
      configuration: z.object({
        administrator_financial_limits: z.record(
          z.string(),
          z.union([z.number(), z.string()]),
        ),
        require_decision_reason: z.literal(true),
      }),
    }),
    z.object({
      ...settingsBaseSchema,
      section: z.literal("notifications"),
      configuration: z.object({
        sla_risk_alerts: z.boolean(),
        review_waiting_alerts: z.boolean(),
        action_recovery_alerts: z.boolean(),
        email_delivery: z.boolean(),
      }),
    }),
    z.object({
      ...settingsBaseSchema,
      section: z.literal("security"),
      configuration: z.object({
        hide_sensitive_customer_fields: z.boolean(),
        session_duration_minutes: z.number().int(),
      }),
    }),
    z.object({
      ...settingsBaseSchema,
      section: z.literal("retention"),
      configuration: z.object({
        audit_retention_days: z.number().int(),
        conversation_retention_days: z.number().int(),
        legal_hold_enabled: z.boolean(),
      }),
    }),
  ]),
});

function mapConnection(
  raw: z.infer<typeof apiConnectionSchema>,
): Connection {
  return ConnectionSchema.parse({
    id: raw.id,
    name: raw.name,
    providerType: raw.provider_type,
    environment: raw.environment,
    health: raw.health,
    lastCheckedAt: raw.last_checked_at,
    credentialStatus: raw.credential_status,
    capabilities: raw.capabilities,
    affectedWork: raw.affected_work,
    version: raw.version,
  });
}

function mapMember(raw: z.infer<typeof apiMemberSchema>): Member {
  return MemberSchema.parse({
    id: raw.id,
    name: raw.name,
    email: raw.email,
    role: raw.role,
    status: raw.status,
    authority: raw.authority,
    lastActiveAt: raw.last_active_at,
    version: raw.version,
  });
}

function mapInvitation(
  raw: z.infer<typeof apiInvitationSchema>,
): Invitation {
  return InvitationSchema.parse({
    id: raw.id,
    email: raw.email,
    role: raw.role,
    status: raw.status,
    version: raw.version,
    invitedBy: raw.invited_by,
    expiresAt: raw.expires_at,
    acceptedAt: raw.accepted_at,
  });
}

function mapSettings(
  raw: z.infer<typeof settingsEnvelopeSchema>["data"],
): OrganizationSettings {
  const base = {
    id: raw.id,
    organizationId: raw.organization_id,
    version: raw.version,
    updatedAt: raw.updated_at,
    usingDefaults: raw.using_defaults,
  };
  if (raw.section === "general") {
    return OrganizationSettingsSchema.parse({
      ...base,
      section: raw.section,
      configuration: {
        organizationName: raw.configuration.organization_name,
        locale: raw.configuration.locale,
        timeZone: raw.configuration.time_zone,
      },
    });
  }
  if (raw.section === "approvals") {
    return OrganizationSettingsSchema.parse({
      ...base,
      section: raw.section,
      configuration: {
        administratorFinancialLimits: Object.fromEntries(
          Object.entries(raw.configuration.administrator_financial_limits).map(
            ([currency, amount]) => [currency, Number(amount)],
          ),
        ),
        requireDecisionReason: raw.configuration.require_decision_reason,
      },
    });
  }
  if (raw.section === "notifications") {
    return OrganizationSettingsSchema.parse({
      ...base,
      section: raw.section,
      configuration: {
        slaRiskAlerts: raw.configuration.sla_risk_alerts,
        reviewWaitingAlerts: raw.configuration.review_waiting_alerts,
        actionRecoveryAlerts: raw.configuration.action_recovery_alerts,
        emailDelivery: raw.configuration.email_delivery,
      },
    });
  }
  if (raw.section === "security") {
    return OrganizationSettingsSchema.parse({
      ...base,
      section: raw.section,
      configuration: {
        hideSensitiveCustomerFields:
          raw.configuration.hide_sensitive_customer_fields,
        sessionDurationMinutes: raw.configuration.session_duration_minutes,
      },
    });
  }
  return OrganizationSettingsSchema.parse({
    ...base,
    section: raw.section,
    configuration: {
      auditRetentionDays: raw.configuration.audit_retention_days,
      conversationRetentionDays:
        raw.configuration.conversation_retention_days,
      legalHoldEnabled: raw.configuration.legal_hold_enabled,
    },
  });
}

const getSessionContext = cache(async () => {
  const session = await apiRequest("/api/session", sessionEnvelopeSchema);
  const organization =
    session.data.organization ??
    (
      await apiRequest(
        "/api/organizations/current",
        organizationEnvelopeSchema,
      )
    ).data;
  return SessionContextSchema.parse({
    actor: {
      id: session.data.id,
      organizationId: session.data.organization_id,
      name: session.data.name,
      role: session.data.role,
      permissions: session.data.permissions,
      authenticationMode: session.data.authentication_mode,
    },
    organization: {
      id: organization.id,
      name: organization.name,
      slug: organization.slug,
      version: organization.version,
      locale: "locale" in organization ? organization.locale : "en-US",
      timeZone: "time_zone" in organization ? organization.time_zone : "UTC",
    },
  });
});

export const apiAdministrationRepository: AdministrationRepository = {
  source: "api",
  getSessionContext,
  async listConnections() {
    const envelope = await apiRequest(
      "/api/connections?limit=100",
      connectionListEnvelopeSchema,
    );
    return envelope.items.map(mapConnection);
  },
  async listMembers() {
    const envelope = await apiRequest(
      "/api/members?limit=100",
      memberListEnvelopeSchema,
    );
    return envelope.items.map(mapMember);
  },
  async listInvitations() {
    const envelope = await apiRequest(
      "/api/invitations",
      invitationListEnvelopeSchema,
    );
    return envelope.items.map(mapInvitation);
  },
  async getSettings(section: SettingsSection) {
    const envelope = await apiRequest(
      `/api/settings/${encodeURIComponent(section)}`,
      settingsEnvelopeSchema,
    );
    return mapSettings(envelope.data);
  },
};
