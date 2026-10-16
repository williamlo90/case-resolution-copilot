# Case Resolution V2 evidence

Release documentation finalized October 16, 2026. V2 extends the governed Decision Brief workflow
with dated SOP rules, approved target changes, independent read-back, acknowledged escalation,
and auditable closure/reopening. This index distinguishes tested application behavior, operator
timing, and hosting evidence.

## Results and reviewer path

Start with the [product case study](../../portfolio/CASE_STUDY.md) and
[evaluation results](RESULTS.md). The sealed synthetic holdout recorded 40/40 policy-correct
and correct-completion outcomes: 19 verified actions and 21 required acknowledged escalations.
The [earlier workflow benchmark](PHASE5_BENCHMARK_REUSE.md) retains its own three-pair timing scope.

For a deeper review, follow the evidence below. Committed aggregates preserve the reported results
after CI artifact expiry; exact revisions, artifact hashes, frozen fixtures, and workflows identify
the original runs. This documentation phase did not rerun the holdout or any paid provider.

| Topic | Evidence and reproduction path |
| --- | --- |
| Product evaluation | [Results](RESULTS.md), [aggregate JSON](results/phase4-holdout.json), [execution protocol](PHASE4_EVALUATION.md), [corpus](../../../backend/evaluations/case_resolution_v2_phase4/) |
| SOP changes | [Typed rules, dated versions and regression](SOP_REVISIONS.md), [18-observation aggregate](results/sop-replay.json), [operator runbook](../../runbooks/sop-change-and-recovery.md) |
| Resolution lifecycle | [Lifecycle contract](LIFECYCLE.md), [measurement definitions](CONTRACT.md), [evaluator](EVALUATOR.md) |
| Human workflow timing | [Benchmark reuse scope](PHASE5_BENCHMARK_REUSE.md), [original report and raw records](../developer-workflow-benchmark/REPORT.md) |
| Container/recovery release | [Phase 6 evidence](PHASE6_RELEASE.md), [demo and hosted-update runbook](../../runbooks/PHASE6_DEMO_RELEASE.md) |
| AWS architecture | [September 25 live validation](../aws-live-validation/README.md), [deployment architecture](../../architecture/AWS_READY_DEPLOYMENT.md) |
| Claim mapping | [Final claim ledger](CLAIM_LEDGER.md), [application wording](../../portfolio/APPLICATION_PACK.md) |

## Run and deployment status

The [demo release guide](../../runbooks/PHASE6_DEMO_RELEASE.md) provides the isolated Docker
Config/Up/Smoke/Down path and evaluator CLI. It also documents how to update the existing
Vercel/Neon/Clerk demo. V2 has not been promoted to that hosted deployment.

AWS infrastructure remains the previously live-validated architecture. The Phase 7 audit found
no executable infrastructure changes since that run; 43 AWS/worker/config unit tests and parsing
of eight lifecycle scripts passed on October 16. No new AWS deployment or AWS performance claim
is needed for this release scope. Live cloud load/reliability validation was not executed.

## Checkpoints and integration

The phase checkpoints are retained on `case-resolution-v2`; Phase 7 live execution was intentionally
omitted. [Phase 8](../../learning/case-resolution-v2/PHASE-8.md) records the final documentation gate.
Integrate through a pull request into `main` while preserving phase commits. The separate candidate
branch identifies container validation; obsolete working branches can be removed after their
required evidence and integration state are retained. No merge or hosted promotion is implied
by the presence of this release documentation.
