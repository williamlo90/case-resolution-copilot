import { ActionDetailSchema, ActionSummarySchema, type ActionDetail, type ActionSummary } from "@/domain/actions/action";

const rawActions = [
  { id: "AC-7001", caseId: "CS-2048", type: "reverse_charge", label: "Reverse duplicate charge", target: "Billing system", impact: { amount: 99, currency: "USD" }, status: "ready", attemptCount: 0, owner: { id: "USR-AR", name: "Alex Rivera" }, updatedAt: "2026-07-21T04:30:00.000Z", recoveryRequired: false },
  { id: "AC-7000", caseId: "CS-2047", type: "verify_settlement", label: "Verify refund settlement", target: "Payments provider", impact: { amount: 145, currency: "USD" }, status: "running", attemptCount: 1, owner: { id: "USR-PS", name: "Priya Shah" }, updatedAt: "2026-07-21T04:24:00.000Z", recoveryRequired: false },
  { id: "AC-6999", caseId: "CS-2043", type: "apply_credit", label: "Apply billing credit", target: "Billing system", impact: { amount: 40, currency: "USD" }, status: "completed", attemptCount: 1, owner: { id: "USR-ET", name: "Elena Torres" }, updatedAt: "2026-07-21T04:09:00.000Z", recoveryRequired: false },
  { id: "AC-6998", caseId: "CS-2045", type: "issue_replacement", label: "Issue replacement order", target: "Order system", impact: { amount: 78, currency: "USD" }, status: "failed_safe", attemptCount: 1, owner: { id: "USR-JM", name: "Jordan Miles" }, updatedAt: "2026-07-21T03:44:00.000Z", recoveryRequired: false },
  { id: "AC-6997", caseId: "CS-2041", type: "issue_compensation", label: "Issue delivery compensation", target: "Payments provider", impact: { amount: 55, currency: "USD" }, status: "outcome_unknown", attemptCount: 1, owner: { id: "USR-AR", name: "Alex Rivera" }, updatedAt: "2026-07-21T03:18:00.000Z", recoveryRequired: true },
  { id: "AC-6996", caseId: "CS-2046", type: "restore_access", label: "Restore account access", target: "Identity provider", impact: null, status: "recovery_required", attemptCount: 2, owner: null, updatedAt: "2026-07-21T02:57:00.000Z", recoveryRequired: true },
] as const;

export const actionSummaryFixtures: readonly ActionSummary[] = ActionSummarySchema.array().parse(rawActions);

export const actionDetailFixtures: readonly ActionDetail[] = actionSummaryFixtures.map((action) => {
  const status = action.status;
  const attempt = action.attemptCount ? [{
    id: `ATT-${action.id.slice(3)}-1`, number: 1, startedAt: "2026-07-21T03:10:00.000Z",
    finishedAt: status === "running" ? null : "2026-07-21T03:11:00.000Z", actor: action.owner?.name ?? "Operations queue",
    outcome: status === "completed" ? "succeeded" : status === "running" ? "running" : status === "outcome_unknown" || status === "recovery_required" ? "unknown" : "failed_before_change",
    detail: status === "completed" ? "Target confirmed the expected result." : status === "failed_safe" ? "Connection failed before the target accepted the request." : status === "outcome_unknown" || status === "recovery_required" ? "The request may have reached the target, but no conclusive response was received." : "Execution is still in progress.",
  }] : [];
  return ActionDetailSchema.parse({
    action,
    approvedProposal: { id: `PROP-${action.caseId.slice(3)}-1`, version: 1, reviewId: `RV-${Number(action.id.slice(3)) - 2000}`, approvedAt: "2026-07-21T03:00:00.000Z" },
    authority: { actor: "Sofia Torres", role: "Support supervisor", rule: "Supervisor approval for consequential changes" },
    typedParameters: { case_reference: action.caseId, amount: action.impact ? `${action.impact.currency} ${action.impact.amount}` : "Not applicable", target_record: `TARGET-${action.id.slice(3)}` },
    targetConnection: { id: `CON-${action.id.slice(3)}`, name: action.target, environment: "demo", health: status === "failed_safe" ? "unavailable" : status === "outcome_unknown" ? "degraded" : "healthy", lastCheckedAt: "2026-07-21T04:29:00.000Z" },
    idempotencyKey: `idem_${action.id.toLocaleLowerCase()}_v1`,
    attempts: attempt,
    receipt: status === "completed" ? { id: `RCT-${action.id.slice(3)}`, externalReference: `EXT-${action.id.slice(3)}`, recordedAt: "2026-07-21T03:11:00.000Z" } : null,
    expectedOutcome: `${action.label} is recorded exactly once in ${action.target}.`,
    observedOutcome: status === "completed" ? `${action.target} confirmed the expected change.` : status === "failed_safe" ? "No target-side change was recorded." : status === "outcome_unknown" || status === "recovery_required" ? "The target-side result has not been verified." : null,
    executionBlocker: status === "failed_safe" ? "connection_unavailable" : status === "recovery_required" ? "expired_approval" : null,
    availableCommands: status === "ready" ? ["execute"] : status === "failed_safe" ? ["retry_safe", "escalate"] : status === "outcome_unknown" ? ["reconcile", "escalate"] : status === "recovery_required" ? ["record_manual_outcome", "escalate"] : [],
  });
});

export const readyActionFixture = actionDetailFixtures[0];
export const safeFailureActionFixture = actionDetailFixtures[3];
export const unknownOutcomeActionFixture = actionDetailFixtures[4];
