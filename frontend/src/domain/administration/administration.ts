import { z } from "zod";

export const ConnectionSchema = z.object({
  id: z.string().regex(/^C(?:N|ON)-[A-Z0-9-]+$/), name: z.string().min(1), providerType: z.string().min(1), environment: z.enum(["demo", "sandbox", "production"]),
  health: z.enum(["healthy", "degraded", "unavailable", "not_configured"]), lastCheckedAt: z.string().datetime().nullable(), credentialStatus: z.enum(["demo", "connected", "missing", "expired"]),
  capabilities: z.object({ read: z.array(z.string()), write: z.array(z.string()) }), affectedWork: z.array(z.string()), version: z.number().int().positive().default(1),
});

export const MemberSchema = z.object({
  id: z.string().regex(/^USR-[A-Z0-9-]+$/), name: z.string().min(1), email: z.string().email(), role: z.enum(["specialist", "supervisor", "administrator", "auditor"]),
  status: z.enum(["active", "invited", "deactivated"]), authority: z.array(z.string()), lastActiveAt: z.string().datetime().nullable(), version: z.number().int().positive().default(1),
});

export const InvitationSchema = z.object({
  id: z.string().min(1),
  email: z.string().email(),
  role: z.enum(["specialist", "supervisor", "administrator", "auditor"]),
  status: z.enum(["pending", "accepted", "expired", "revoked"]),
  version: z.number().int().positive(),
  invitedBy: z.string().min(1),
  expiresAt: z.string().datetime(),
  acceptedAt: z.string().datetime().nullable(),
});

export const OnboardingStepSchema = z.object({ id: z.string().min(1), label: z.string().min(1), description: z.string().min(1), status: z.enum(["complete", "current", "pending", "skipped"]) });

export const SessionContextSchema = z.object({
  actor: z.object({
    id: z.string().min(1),
    organizationId: z.string().min(1),
    name: z.string().min(1),
    role: z.enum(["specialist", "supervisor", "administrator", "auditor"]).nullable(),
    permissions: z.array(z.string().min(1)),
    authenticationMode: z.enum(["deterministic_development", "provider"]),
  }),
  organization: z.object({
    id: z.string().min(1),
    name: z.string().min(1),
    slug: z.string().min(1),
    version: z.number().int().positive(),
    locale: z.string().min(1),
    timeZone: z.string().min(1),
  }),
});

const SettingsBaseSchema = z.object({
  id: z.string().min(1),
  organizationId: z.string().min(1),
  version: z.number().int().positive(),
  updatedAt: z.string().datetime(),
  usingDefaults: z.boolean(),
});

export const OrganizationSettingsSchema = z.discriminatedUnion("section", [
  SettingsBaseSchema.extend({
    section: z.literal("general"),
    configuration: z.object({
      organizationName: z.string().min(1),
      locale: z.string().min(1),
      timeZone: z.string().min(1),
    }),
  }),
  SettingsBaseSchema.extend({
    section: z.literal("approvals"),
    configuration: z.object({
      administratorFinancialLimits: z.record(
        z.string().regex(/^[A-Z]{3}$/),
        z.number().positive(),
      ),
      requireDecisionReason: z.literal(true),
    }),
  }),
  SettingsBaseSchema.extend({
    section: z.literal("notifications"),
    configuration: z.object({
      slaRiskAlerts: z.boolean(),
      reviewWaitingAlerts: z.boolean(),
      actionRecoveryAlerts: z.boolean(),
      emailDelivery: z.boolean(),
    }),
  }),
  SettingsBaseSchema.extend({
    section: z.literal("security"),
    configuration: z.object({
      hideSensitiveCustomerFields: z.boolean(),
      sessionDurationMinutes: z.number().int().min(15).max(1440),
    }),
  }),
  SettingsBaseSchema.extend({
    section: z.literal("retention"),
    configuration: z.object({
      auditRetentionDays: z.number().int().min(365).max(3650),
      conversationRetentionDays: z.number().int().min(30).max(3650),
      legalHoldEnabled: z.boolean(),
    }),
  }),
]);

export type Connection = z.infer<typeof ConnectionSchema>;
export type Member = z.infer<typeof MemberSchema>;
export type Invitation = z.infer<typeof InvitationSchema>;
export type OnboardingStep = z.infer<typeof OnboardingStepSchema>;
export type SessionContext = z.infer<typeof SessionContextSchema>;
export type OrganizationSettings = z.infer<typeof OrganizationSettingsSchema>;
export type SettingsSection = OrganizationSettings["section"];
