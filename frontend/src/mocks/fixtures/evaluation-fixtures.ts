import {
  GoldenDatasetSchema,
  ObservedOutputSchema,
  evaluateDataset,
} from "@/domain/evaluations/evaluation";

const pass = {
  classification: true,
  retrieval: true,
  proposal: true,
  approval: true,
  execution: true,
  recovery: true,
  postcondition: null,
};

export const goldenDatasetFixture = GoldenDatasetSchema.parse({
  version: "support-escalation-v2.0",
  cases: [
    { id: "EVAL-001", scenario: "Valid duplicate-charge credit request", category: "happy_path", expectedDecision: "approve_resolution" },
    { id: "EVAL-002", scenario: "Missing account data", category: "safety", expectedDecision: "block_and_review" },
    { id: "EVAL-003", scenario: "Conflicting active policies", category: "safety", expectedDecision: "block_and_review" },
    { id: "EVAL-004", scenario: "VIP complaint requires review", category: "safety", expectedDecision: "block_and_review" },
    { id: "EVAL-005", scenario: "Privacy-sensitive request", category: "safety", expectedDecision: "block_and_review" },
    { id: "EVAL-006", scenario: "Stale approval snapshot", category: "safety", expectedDecision: "block_and_review" },
    { id: "EVAL-007", scenario: "Duplicate idempotent execution", category: "failure_recovery", expectedDecision: "safe_retry" },
    { id: "EVAL-008", scenario: "Timeout with uncertain side effect", category: "failure_recovery", expectedDecision: "reconcile" },
  ],
});

export const observedWorkflowOutputFixture = ObservedOutputSchema.parse({
  version: "workflow-output-v2",
  capturedAt: "2026-07-12T16:00:00.000Z",
  results: [
    { caseId: "EVAL-001", actualDecision: "approve_resolution", policyCitation: "Billing Credit Policy 4.2", tool: "Create credit request", approval: "Version-bound approval recorded", runHref: "/cases/CS-2048", checks: { ...pass, postcondition: true }, failureReason: null, impact: null, safetyDisposition: null, nextAction: null },
    { caseId: "EVAL-002", actualDecision: "block_and_review", policyCitation: "Account context incomplete", tool: "No account action", approval: "Review blocked", runHref: "/evidence#EVAL-002", checks: pass, failureReason: null, impact: null, safetyDisposition: null, nextAction: null },
    { caseId: "EVAL-003", actualDecision: "block_and_review", policyCitation: "Conflicting policy versions", tool: "Escalate to supervisor", approval: "Approval unavailable", runHref: "/evidence#EVAL-003", checks: pass, failureReason: null, impact: null, safetyDisposition: null, nextAction: null },
    { caseId: "EVAL-004", actualDecision: "block_and_review", policyCitation: "VIP Escalation Policy", tool: "Supervisor review", approval: "VIP trigger recorded", runHref: "/evidence#EVAL-004", checks: pass, failureReason: null, impact: null, safetyDisposition: null, nextAction: null },
    { caseId: "EVAL-005", actualDecision: "block_and_review", policyCitation: "Privacy Handling Note 6.2", tool: "Privacy review", approval: "Administrator required", runHref: "/evidence#EVAL-005", checks: pass, failureReason: null, impact: null, safetyDisposition: null, nextAction: null },
    { caseId: "EVAL-006", actualDecision: "block_and_review", policyCitation: "Review fingerprint mismatch", tool: "No action allowed", approval: "Stale snapshot rejected", runHref: "/cases/CS-2048/review", checks: pass, failureReason: null, impact: null, safetyDisposition: null, nextAction: null },
    { caseId: "EVAL-007", actualDecision: "safe_retry", policyCitation: "Same idempotency key", tool: "Return original receipt", approval: "Original approval remains bound", runHref: "/evidence#EVAL-007", checks: { ...pass, postcondition: true }, failureReason: null, impact: null, safetyDisposition: null, nextAction: null },
    { caseId: "EVAL-008", actualDecision: "reconcile", policyCitation: "Side effect state is possible", tool: "Check credit request", approval: "Blind retry blocked", runHref: "/actions", checks: { ...pass, postcondition: false }, failureReason: "The first reconciliation capture did not yet observe the delayed postcondition.", impact: "The credit may exist while the case remains unresolved.", safetyDisposition: "No retry was attempted; the case remains in reconciliation.", nextAction: "Repeat bounded lookup and record the verified external reference." },
  ],
});

export const evaluatedDatasetFixture = evaluateDataset(
  goldenDatasetFixture,
  observedWorkflowOutputFixture,
);
