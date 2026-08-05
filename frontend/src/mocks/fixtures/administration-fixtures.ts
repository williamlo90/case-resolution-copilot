import { ConnectionSchema, InvitationSchema, MemberSchema, OnboardingStepSchema, type Connection, type Invitation, type Member, type OnboardingStep } from "@/domain/administration/administration";

export const connectionFixtures: readonly Connection[] = ConnectionSchema.array().parse([
  { id: "CON-1004", name: "Billing system", providerType: "Billing", environment: "demo", health: "healthy", lastCheckedAt: "2026-07-21T04:25:00.000Z", credentialStatus: "demo", capabilities: { read: ["Invoices", "Payments", "Subscriptions"], write: ["Reverse charge", "Apply credit"] }, affectedWork: ["Billing disputes", "Refund requests"] },
  { id: "CON-1003", name: "Support inbox", providerType: "Customer support", environment: "demo", health: "healthy", lastCheckedAt: "2026-07-21T04:24:00.000Z", credentialStatus: "demo", capabilities: { read: ["Conversations", "Attachments"], write: ["Reply", "Internal note"] }, affectedWork: ["All cases"] },
  { id: "CON-1002", name: "Identity provider", providerType: "Identity", environment: "sandbox", health: "degraded", lastCheckedAt: "2026-07-21T03:54:00.000Z", credentialStatus: "connected", capabilities: { read: ["Account state", "Security events"], write: ["Restore access"] }, affectedWork: ["Account access"] },
  { id: "CON-1001", name: "Order system", providerType: "Orders", environment: "production", health: "not_configured", lastCheckedAt: null, credentialStatus: "missing", capabilities: { read: ["Orders", "Deliveries"], write: ["Issue replacement"] }, affectedWork: ["Service exceptions"] },
]);

export const memberFixtures: readonly Member[] = MemberSchema.array().parse([
  { id: "USR-1004", name: "Alex Rivera", email: "alex.rivera@example.com", role: "specialist", status: "active", authority: ["Investigate cases", "Submit proposals"], lastActiveAt: "2026-07-21T04:30:00.000Z" },
  { id: "USR-1003", name: "Sofia Torres", email: "sofia.torres@example.com", role: "supervisor", status: "active", authority: ["Decide reviews", "Recover actions"], lastActiveAt: "2026-07-21T04:18:00.000Z" },
  { id: "USR-1002", name: "Avery Daniels", email: "avery.daniels@example.com", role: "administrator", status: "active", authority: ["Manage policies", "Manage organization"], lastActiveAt: "2026-07-21T03:52:00.000Z" },
  { id: "USR-1001", name: "Morgan Lee", email: "morgan.lee@example.com", role: "auditor", status: "invited", authority: ["Read audit evidence", "Export case audit"], lastActiveAt: null },
]);

export const invitationFixtures: readonly Invitation[] = InvitationSchema.array().parse([
  {
    id: "INV-1001",
    email: "new.supervisor@example.com",
    role: "supervisor",
    status: "pending",
    version: 1,
    invitedBy: "USR-1002",
    expiresAt: "2026-08-04T03:52:00.000Z",
    acceptedAt: null,
  },
]);

export const onboardingStepFixtures: readonly OnboardingStep[] = OnboardingStepSchema.array().parse([
  { id: "workspace", label: "Workspace details", description: "Name the organization and choose its operating time zone.", status: "complete" },
  { id: "team", label: "Operating team", description: "Keep an active reviewer available.", status: "complete" },
  { id: "policy", label: "Published policy", description: "Publish at least one policy.", status: "current" },
  { id: "case_source", label: "Case source", description: "Confirm cases reach the workspace.", status: "pending" },
  { id: "action_target", label: "Action target", description: "Verify a tool for controlled changes.", status: "pending" },
  { id: "approval_rule", label: "Approval rule", description: "Confirm approval limits.", status: "pending" },
  { id: "test_case", label: "Configuration test", description: "Generate one Decision Brief.", status: "pending" },
  { id: "activation", label: "Workspace ready", description: "Complete every required check.", status: "pending" },
]);
