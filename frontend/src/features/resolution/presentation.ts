import type { Resolution } from "./contract";

export function resolutionHeading(data: Resolution): string {
  if (data.status === "completed") return "Case closed";
  if (data.closure.eligible) return "Outcome verified";
  if (data.actions.some(a => a.status === "outcome_unknown" || a.status === "recovery_required" || a.status === "running")) return "Outcome uncertain: check before trying again";
  if (data.events.some(e => e.kind === "action_verified")) return "Outcome needs a fresh check";
  return "Outcome not checked yet";
}
