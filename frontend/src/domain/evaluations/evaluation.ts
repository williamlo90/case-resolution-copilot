import { z } from "zod";

export const EvaluationDecisionSchema = z.enum([
  "approve_resolution",
  "block_and_review",
  "safe_retry",
  "reconcile",
]);

export const EvaluationCheckSchema = z.object({
  classification: z.boolean(),
  retrieval: z.boolean(),
  proposal: z.boolean(),
  approval: z.boolean(),
  execution: z.boolean(),
  recovery: z.boolean(),
  postcondition: z.boolean().nullable(),
});

export const GoldenCaseSchema = z.object({
  id: z.string().regex(/^EVAL-\d{3}$/),
  scenario: z.string().min(1),
  category: z.enum(["happy_path", "safety", "failure_recovery"]),
  expectedDecision: EvaluationDecisionSchema,
});

export const GoldenDatasetSchema = z.object({
  version: z.string().regex(/^support-escalation-v\d+\.\d+$/),
  cases: GoldenCaseSchema.array().min(1),
});

export const ObservedResultSchema = z.object({
  caseId: z.string().regex(/^EVAL-\d{3}$/),
  actualDecision: EvaluationDecisionSchema,
  policyCitation: z.string().min(1),
  tool: z.string().min(1),
  approval: z.string().min(1),
  runHref: z.string().startsWith("/"),
  checks: EvaluationCheckSchema,
  failureReason: z.string().nullable(),
  impact: z.string().nullable(),
  safetyDisposition: z.string().nullable(),
  nextAction: z.string().nullable(),
});

export const ObservedOutputSchema = z.object({
  version: z.string().regex(/^workflow-output-v\d+$/),
  capturedAt: z.string().datetime(),
  results: ObservedResultSchema.array().min(1),
});

export type GoldenDataset = z.infer<typeof GoldenDatasetSchema>;
export type ObservedOutput = z.infer<typeof ObservedOutputSchema>;
export type EvaluationCase = z.infer<typeof GoldenCaseSchema> &
  Omit<z.infer<typeof ObservedResultSchema>, "caseId">;

export type EvaluatedCase = EvaluationCase & {
  result: "passed" | "failed";
  failedChecks: string[];
};

export function evaluateCase(testCase: EvaluationCase): EvaluatedCase {
  const failedChecks: string[] = [];

  if (testCase.expectedDecision !== testCase.actualDecision) {
    failedChecks.push("decision_match");
  }

  for (const [name, value] of Object.entries(testCase.checks)) {
    if (value === false) failedChecks.push(name);
  }

  return {
    ...testCase,
    result: failedChecks.length === 0 ? "passed" : "failed",
    failedChecks,
  };
}

export function evaluateDataset(
  goldenDataset: GoldenDataset,
  observedOutput: ObservedOutput,
) {
  const observedByCase = new Map(
    observedOutput.results.map((result) => [result.caseId, result]),
  );

  const cases = goldenDataset.cases.map((goldenCase) => {
    const observed = observedByCase.get(goldenCase.id);
    if (!observed) {
      throw new Error(`Missing observed result for ${goldenCase.id}`);
    }
    const { caseId: _caseId, ...observedFields } = observed;
    void _caseId;
    return evaluateCase({ ...goldenCase, ...observedFields });
  });

  const passed = cases.filter((item) => item.result === "passed").length;

  return {
    goldenVersion: goldenDataset.version,
    observedVersion: observedOutput.version,
    evaluatedAt: observedOutput.capturedAt,
    evaluator: "deterministic_rule_evaluator_v2" as const,
    cases,
    summary: {
      total: cases.length,
      passed,
      failed: cases.length - passed,
      passRate: Math.round((passed / cases.length) * 100),
    },
  };
}
