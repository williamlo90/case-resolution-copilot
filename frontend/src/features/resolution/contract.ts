import { z } from "zod";

export const resolutionKindSchema = z.enum(["completed", "reopened", "escalation_routed", "escalation_acknowledged"]);
export const resolutionSchema = z.object({
  case_id: z.string(),
  version: z.number().int().positive(),
  status: z.string(),
  closure: z.object({ eligible: z.boolean(), blocker: z.string().nullable(), verification_ids: z.array(z.string()) }),
  available_commands: z.array(resolutionKindSchema),
  actions: z.array(z.object({ id: z.string(), status: z.string() })),
  events: z.array(z.object({
    id: z.string(), kind: z.string(), at: z.string(), actor_id: z.string(),
    previous_event_id: z.string().nullable(), data: z.record(z.string(), z.unknown()),
  })),
});
export type Resolution = z.infer<typeof resolutionSchema>;
export type ResolutionKind = z.infer<typeof resolutionKindSchema>;
