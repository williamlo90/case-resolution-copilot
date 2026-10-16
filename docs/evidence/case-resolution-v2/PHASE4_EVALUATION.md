# Phase 4 product evaluation

The Phase 4 lane exercises the actual case, governed-policy, decision, review,
action, read-back, escalation and resolution APIs against disposable PostgreSQL
and a deterministic synthetic target. It does not measure a live payment or
identity provider. Provider calls and measured provider cost are zero; cloud
runner infrastructure cost is unmeasured.

The [Phase 4 corpus](../../../backend/evaluations/case_resolution_v2_phase4/)
contains 24 exposed development cases, three regression cases and a separate
sealed 40-case holdout (14 billing, 13 refund, 13 account recovery). Cases use
source facts, explicit operation destinations and policy versions. Labels were
agent-authored and reviewed by the implementation agent, not an independent
human adjudicator. The original Phase 2 corpus is retained separately and was
not used for the Phase 4 product run.

Each synthetic case supplies a decision scope from its input family. Policy
retrieval narrows to that scope, so one case cannot cite another family's
authority merely because their wording is similar. A publication rejected for
overlapping authority blocks that scope pending review.

The [isolated CI workflow](../../../.github/workflows/phase4-product-evaluation.yml)
packages only input files and source code for runtime jobs. The runtime cannot
read labels. For each case it persists the product observation, then seals the
scheduled population and observation hashes. A later job checks hashes and
scores against labels. The exposed development gate must pass before the
holdout capture job starts. Every run artifact records the exact commit, seed,
manifest, evaluator identity, all missing/invalid cases and component grades.

Acceptance requires policy correctness at least 95%, correct completion at
least 90%, zero critical unsafe cases, and zero missing, invalid or provider
failure observations. The gate file in the CI artifact contains exact
numerators and denominators. A failed holdout is never rescored as a blind
test; a new holdout revision is needed for a later final claim.

Operational reporting includes actual escalation and acknowledgement, verified
action read-back, duplicate dispatch prevention, simulated day-7/day-30 reopen,
end-to-end and API latency sample counts with p50/p90/p95 only when at least
100 samples exist, and cost per verified correct resolution. Worker/provider
latency and infrastructure or combined cost stay N/A without measurements.
Simulated reopen is not 30 days of production observation. Human approval is
required for every consequential action; the workflow does not establish a
hands-free automation rate or a new handling-time claim. [Phase 5](PHASE5_BENCHMARK_REUSE.md)
reuses the completed historical decision-workflow benchmark with its original measurement scope.

The runnable result is the `phase4-gate.json`, `report.json`,
`operations-report.json`, sealed observations and run contract attached to
the [Phase 4 workflow runs](https://github.com/williamlo90/case-resolution-copilot/actions/workflows/phase4-product-evaluation.yml).
The artifact's exact commit and gate status govern any numerical claim; the
existence of this protocol alone is not a passing result.

The finalized [results page](RESULTS.md) and [committed aggregate](results/phase4-holdout.json)
record the passing October 14 run, including its exact source and artifact hashes.
