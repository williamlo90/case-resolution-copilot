# Case Resolution Copilot - Evaluation V1 Implementation Plan

Status: Evaluation V1 complete. Deterministic regression, bounded provider canary, and guarded persisted-workflow validation were executed on 2026-09-30.

## Objective

Build a frozen, auditable automated benchmark for the current Case Resolution Copilot without changing prompts, retrieval behavior, orchestration, or production decisions. Evaluation V1 contains exactly 10 synthetic cases and supports two immutable observations per case.

This benchmark measures automated decision quality and workflow safety. It does not replace or reinterpret the earlier human workflow timing pilot.

## Phase Status

| Item | Status |
| --- | --- |
| Map the production workflow | completed |
| Inventory existing evaluation components | completed |
| Define isolation and cost controls | completed |
| Define the V1 benchmark architecture | completed |
| Generate candidate cases | completed |
| Review gold labels before execution | completed |
| Freeze the 10-case benchmark | completed |
| Implement prediction and grading harnesses | completed |
| Execute deterministic preflight | completed |
| Execute bounded provider canary | completed |
| Execute guarded persisted-workflow validation | completed |
| Methodology audit and public evidence | completed |

## Production Workflow Under Test

The production decision path is composed rather than exposed as one callable:

1. Load the persisted case workspace.
2. Refresh governed policy evidence through `PolicyEvidenceService`.
3. Compute context, evidence, and decision-input fingerprints.
4. Acquire the decision-generation lease.
5. Run `LangGraphDecisionOrchestrator`, delegating server-owned controls to the deterministic engine and optional narrative fields to OpenAI.
6. Verify checkpoint lineage and evidence freshness.
7. Persist an immutable Decision Brief.
8. Submit and decide a human review when the proposal is eligible.
9. Materialize and execute only approved controlled actions.

The HTTP generation entry point is `app.api.routes.decision_briefs.generate_decision_brief`. The core preparation and persistence boundary is `DecisionBriefService`. `DecisionAnalysis` is the authoritative output contract.

## Evaluation Architecture

Evaluation V1 will add a separate package rather than changing the existing three-case Decision Brief gate:

```text
backend/app/evaluation/case_resolution/
  models.py
  validation.py
  generation.py
  scoring.py
  reporting.py
  runner.py

backend/evaluations/case_resolution_v1/
  manifest.json
  inputs.jsonl
  labels.jsonl
  README.md

backend/.benchmark-data/case_resolution_v1/runs/<run-id>/
  contract.json
  progress.json
  observations.jsonl
  observation-manifest.json
  judge-results.jsonl
  report.json
  report.md
```

Committed benchmark inputs and labels are frozen before execution. Runtime outputs remain under the ignored `.benchmark-data` directory. The runner must reject hash mismatches, duplicate case IDs, a case count other than 10, and a repeat count other than 2 for a complete run.

## Separation Of Responsibilities

Independent roles will be used for benchmark construction and review:

- Evaluation Designer defines dimensions, deterministic failure rules, and reporting semantics.
- Test Case Generator creates candidates without seeing system outputs.
- Gold-label review accepts, corrects, or rejects candidates before any execution; V1 did not retain a separate reviewer-provenance artifact.
- Harness Engineer implements input-only generation, scoring, repeats, and reports.
- Independent Judge scores only genuinely semantic properties with a strict structured rubric.
- Evaluation Auditor checks leakage, circularity, ambiguity, weak grading, and inflated claims.

The model under test never creates or edits its own expected answers. Deterministic critical failures cannot be overturned by the semantic judge.

## Benchmark Composition

The frozen suite will contain:

- 3 normal/common cases
- 2 missing-information cases
- 2 conflicting-evidence cases
- 1 policy-heavy case
- 1 noisy-evidence case
- 1 adversarial or safety case

Each case will use repository-native case, workspace, policy, evidence, decision, review, and action terminology. Every gold label must define the expected resolution, required evidence and policy references, required and forbidden actions, escalation behavior, forbidden claims, and grader notes.

Ambiguous candidates without a defensible expected behavior will be rejected and replaced before the manifest is frozen.

## Execution Lanes

### Lane A - Deterministic preflight

- Uses deterministic model, embeddings, retrieval, and action target.
- Requires no OpenAI call.
- Runs schema, freeze, grading, report, retry, and failure-path tests.
- Uses no application database for the initial engine-level lane.

### Lane B - Production-shaped decision evaluation

- Uses the production `LangGraphDecisionOrchestrator` around the selected decision engine.
- Executes 10 cases twice, producing 20 immutable observations.
- Records output schema, fingerprints, latency, retries/failures, token usage, estimated cost, and control preservation.
- Uses deterministic retrieval in V1 so embedding cost and retrieval variability do not obscure decision evaluation.

### Lane C - Persisted workflow validation

- Uses the real API/service boundaries against a disposable migrated PostgreSQL database only.
- Exercises generation, review submission, review decision, action materialization, and deterministic execution/reconciliation where the case requires it.
- Must run through `scripts/run_integration_tests.ps1`; direct destructive integration-test invocation is prohibited.

Lane C validates workflow behavior but does not need two paid model calls per case if the frozen Decision Brief observation can be replayed safely into downstream review/action validation.

## Grading

Deterministic graders own:

- expected control state and disposition
- required evidence-ID coverage
- required policy ID/version/clause retrieval coverage
- escalation or information-needed state
- required and forbidden actions
- unsupported factual claims that can be enumerated from the gold label
- schema validity
- approval and action safety
- critical failures

The optional LLM judge is limited to semantic completeness and clarity that cannot be represented reliably as exact constraints. It returns `pass`, a `0-1` score, `reason`, and `critical_error`. Its result is reported separately and cannot erase a deterministic failure.

## Metrics

The final report will include:

- control-state accuracy
- required evidence coverage rate
- required policy-retrieval coverage rate
- unsupported-claim rate
- escalation accuracy
- required-action and forbidden-action pass rates
- schema-validity rate
- deterministic critical-failure count
- LLM-judge pass rate, when executed
- P50 and P95 latency
- average provider cost per observation, when measurable
- run-to-run consistency
- per-case and per-repeat results

Regression thresholds are provisional and will be labelled as such. They are not statistically validated by a 10-case synthetic suite.

## Cost And Safety Gate

No paid run may begin until the exact configured model pricing is recorded with its source and checked date.

Maximum planned paid calls for a complete V1 run:

- model under test: 20 calls maximum
- semantic judge: 20 calls maximum
- total: 40 calls maximum
- paid embeddings: 0 in V1

The runner must have explicit call ceilings, zero SDK retries for benchmark calls, unique write-once run IDs, resumable progress, and stop conditions for authentication failures, missing usage records, consecutive provider failures, cost ceiling breaches, safety failures, or control-preservation failures.

Historical evidence suggests a low narrative-generation cost, but it is not a current quote and cannot authorize the run. A current estimate and contingency reserve are required first.

Resource policy remains active: no local browser automation, dev server, load test, or 20-run local benchmark loop. Repeated provider execution belongs in an isolated CI/container job with bounded resources and spend.

## Existing Components To Reuse

- Strict Pydantic contracts and control-preservation checks from the Decision Brief evaluator.
- Canonical JSON, SHA-256, path guards, and atomic writes from `public_benchmark.storage`.
- Input-only prediction followed by label-aware scoring from the public benchmark runner.
- Frozen input/label manifest patterns from Retrieval V2.
- Workflow proof concepts from the workflow traceability matrix.
- Provider token and cost records from `provider_cost` and `OpenAIDecisionNarrativeGateway`.

The existing Decision Brief, retrieval, public-data, workflow-traceability, and human-timing evaluations remain unchanged and keep their current meanings.

## Completed Build Order

1. Define strict case, label, observation, repeat, judge, and report schemas.
2. Generate more than 10 candidates without running the product.
3. Review the gold labels before execution and select exactly 10 unambiguous cases.
4. Freeze inputs, labels, policy corpus, manifest hashes, product revision, and evaluator revision.
5. Implement input-only generation through the production-shaped orchestration path.
6. Implement label-aware deterministic scoring and structured semantic judging.
7. Add focused unit and contract tests.
8. Run the deterministic preflight and inspect raw artifacts.
9. Record current model pricing and run a two-call provider canary with zero SDK retries.
10. Run four guarded PostgreSQL workflow scenarios through the repository integration runner.

## Final V1 Evidence

- The final deterministic result is a 20-observation post-fix regression validation, not a blind holdout.
- The provider canary used two OpenAI calls across three cases; the policy-missing case correctly skipped the provider.
- The persisted lane passed conflict blocking, snapshot-bound approval, exactly-once execution, and unknown-outcome reconciliation.
- Public, sanitized results and the methodology audit live in `docs/evidence/case-resolution-evaluation-v1/`.
- Exact semantic fact phrasing, exact information-gap wording, full action-parameter equality, and persisted review boundaries remain outside the aggregate deterministic score.

## Known Limitations

- The benchmark is synthetic and contains only 10 cases.
- Two repeats provide only a basic consistency signal and limited evidence about variability.
- An LLM judge can introduce bias even with a strict rubric.
- Engine-level evaluation does not by itself prove persisted review/action correctness.
- Automated latency is not human productivity evidence.
- Results cannot claim real-world user impact or replace controlled human workflow testing.
