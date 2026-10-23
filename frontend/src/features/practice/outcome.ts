type OutcomeInput = {
  action: {action: {id: string; status: string}; receipt: {external_reference: string} | null} | null;
  lifecycle: {events: {kind: string; data: Record<string, unknown>}[]};
};
export function practiceOutcome(view: OutcomeInput): "verified" | "acknowledged" | "uncertain" | "unchecked" {
  if (!view.action) return "unchecked";
  const {action, receipt} = view.action;
  if (action.status === "completed" && view.lifecycle.events.some(e => e.kind === "action_verified" && e.data.action_id === action.id)) return "verified";
  if (action.status === "outcome_unknown" && receipt) return "acknowledged";
  if (["outcome_unknown", "recovery_required", "running"].includes(action.status)) return "uncertain";
  return "unchecked";
}
