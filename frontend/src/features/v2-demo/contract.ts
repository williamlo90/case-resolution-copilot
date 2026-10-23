import { z } from "zod";

export const scenarioSchema = z.enum(["verified_reopen", "sop_revision", "timeout_recovery"]);
export type DemoScenario = z.infer<typeof scenarioSchema>;
export const demoRoleSchema = z.enum(["specialist", "reviewer", "policy_manager"]);
export type DemoRole = z.infer<typeof demoRoleSchema>;
export const demoCommandSchema = z.object({
  command: z.enum(["generate", "submit", "reserve", "approve", "execute", "reconcile", "close", "reopen", "publish_revision", "rollback", "route_escalation", "acknowledge"]),
  role: demoRoleSchema,
  expected_version: z.number().int().positive(),
  command_id: z.string().min(16).max(128),
  snapshot_fingerprint: z.string().length(64).nullable(),
  reason: z.string().trim().min(3).max(1000),
  reference: z.string().trim().min(1).max(200).nullable(),
  resource_id: z.string().min(1).max(64).nullable(),
  expected_proposal_version: z.number().int().positive().nullable(),
});
export type DemoCommand = z.infer<typeof demoCommandSchema>;
export const demoSessionSchema = z.object({
  session_id: z.string().regex(/^VD-[A-F0-9]{16}$/), scenario: scenarioSchema,
  case_id: z.string(), created_at: z.string(),
});
export type DemoSession = z.infer<typeof demoSessionSchema>;
const proposalSchema = z.object({ version: z.number(), outcome: z.string(), rationale: z.string(), state: z.string(), evidence_ids: z.array(z.string()), model_version: z.string() });
export const demoViewSchema = z.object({
  session: demoSessionSchema,
  case: z.object({ id: z.string(), version: z.number(), status: z.string(), issue: z.string(), request: z.string(), records: z.array(z.object({ id: z.string(), reference: z.string(), fields: z.record(z.string(), z.string()) })) }),
  policy: z.object({ policy: z.object({ id: z.string(), current_version: z.number(), version: z.number() }), versions: z.array(z.object({ version: z.number(), status: z.string(), source_text: z.string(), effective_from: z.string().nullable() })) }),
  brief: z.object({ proposal: proposalSchema, facts: z.array(z.object({ statement: z.string(), source: z.string() })), missing_information: z.array(z.object({ label: z.string(), description: z.string() })), response_draft: z.object({ subject: z.string(), body: z.string() }) }).nullable(),
  review: z.object({ review: z.object({ id: z.string(), status: z.string(), version: z.number(), snapshot_fingerprint: z.string(), snapshot_freshness: z.object({ status: z.string(), reason: z.string().nullable() }), submitted_by: z.object({ name: z.string() }) }), evidence: z.array(z.object({ id: z.string(), citation: z.string(), excerpt: z.string(), policy_version: z.number() })), decision_history: z.array(z.object({ reason: z.string(), actor: z.object({ name: z.string() }), decided_at: z.string() })) }).nullable(),
  action: z.object({ action: z.object({ id: z.string(), status: z.string(), version: z.number(), attempt_count: z.number() }), idempotency_key: z.string(), typed_parameters: z.record(z.string(), z.string()), execution_blocker: z.string().nullable(), observed_outcome: z.string().nullable(), receipt: z.object({ external_reference: z.string() }).nullable() }).nullable(),
  target: z.object({ objects: z.record(z.string(), z.record(z.string(), z.string())), effect_count: z.number(), operations: z.array(z.object({ operation_id: z.string(), target: z.string(), changes: z.record(z.string(), z.string()) })), storage: z.string() }),
  lifecycle: z.object({ version: z.number(), status: z.string(), events: z.array(z.object({ id: z.string(), kind: z.string(), at: z.string(), actor_id: z.string(), previous_event_id: z.string().nullable(), data: z.record(z.string(), z.unknown()) })) }),
  observations: z.array(z.object({ simulated_role: z.string(), command: z.string(), outcome: z.string(), at: z.string() })),
});
export type DemoView = z.infer<typeof demoViewSchema>;
export const demoEnvelopeSchema = z.object({ data: demoViewSchema });
export const demoSessionsSchema = z.object({ items: z.array(demoSessionSchema) });

export const scenarios: { id: DemoScenario; title: string; task: string }[] = [
  { id: "verified_reopen", title: "1 · Verified resolution & reopen", task: "Prepare → submit → reserve → approve → execute → read back → close → reopen. Prove a receipt alone cannot close the case." },
  { id: "sop_revision", title: "2 · SOP revision & rollback", task: "Approve under v1 → publish v2 → try the old action → publish rollback v3 → try again. Both attempts must be blocked with zero effects." },
  { id: "timeout_recovery", title: "3 · Timeout & safe recovery", task: "Approve → execute (timeout after commit) → try execute again → reconcile. The original operation must have exactly one effect. Then close with verified proof." },
];
