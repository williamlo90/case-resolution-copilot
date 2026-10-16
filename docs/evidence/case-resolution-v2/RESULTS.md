# V2 evaluation results

The [isolated product run](https://github.com/williamlo90/case-resolution-copilot/actions/runs/38513662226)
passed on October 14, 2026, at source `1463826baff0195d2aa173c1d0aa5900deed5fd7`.
The test used real case/policy/decision/review/action/resolution APIs backed by disposable
PostgreSQL, a deterministic decision engine, and synthetic billing/identity targets.

## Sealed synthetic holdout

| Metric | Result |
| --- | ---: |
| Scheduled and observed cases | 40/40 |
| Policy-correct cases | 40/40 |
| Correct terminal completion | 40/40 |
| Verified target actions | 19/19 required |
| Routed and acknowledged escalations | 21/21 required |
| Critical unsafe cases | 0/40 |
| Missing / invalid / provider failures | 0 / 0 / 0 |
| Duplicate dispatches blocked | 4 |
| Simulated day-7 reopen / day-30 reopen | 4/4 at each window |

The sample comprises 14 billing, 13 refund, and 13 account-recovery cases. Labels were authored
and reviewed by the implementation agent, not independently adjudicated by human reviewers.
The runtime saved observations before scoring labels in a separate job. The 95% Wilson interval
for each 40/40 case-level rate is approximately 91.2â€“100%; it describes this synthetic sample.
Simulated reopen is a recovery exercise, not a production reopen-rate estimate.

The [committed aggregate](results/phase4-holdout.json) retains exact counts, run identity,
intervals and source artifact hashes. The [protocol](PHASE4_EVALUATION.md) and
[frozen corpus](../../../backend/evaluations/case_resolution_v2_phase4/) describe the
method and acceptance thresholds. The separately scored exposed development set recorded
23/24 policy-correct and correct-completion outcomes; its result is not pooled with holdout.

## Operational measurements

The run recorded 468 API samples: p50 21.8 ms, p90 86.9 ms, p95 100.8 ms in the isolated
synthetic CI environment. Forty end-to-end cases are insufficient for a headline p95 under
the frozen contract. Worker/provider latency and combined infrastructure/provider cost per
resolution are unmeasured. Provider calls and measured provider cost were zero because this
lane was deterministic; that is not a zero-cost production inference claim.

All consequential actions required human approval in the workflow. This run does not establish
hands-free automation. Payment and identity changes affected synthetic targets, not live accounts.

## Dated SOP regression

The [Phase 3 replay](https://github.com/williamlo90/case-resolution-copilot/actions/runs/38507144879)
at `2f0894221c5160500fac1cb9b265947f69cb30bc` on October 14 recorded 18/18 correct exposed
observations: six cases across three simulated policy dates. Three rule families each have three
immutable versions, for nine source versions; each family/version had 2/2 correct observations.
See the [aggregate](results/sop-replay.json) and [rule/failure analysis](SOP_REVISIONS.md).
This is decision regression, not a second holdout or a payment-completion measurement.

## Separate supporting evidence

- [Operator benchmark](PHASE5_BENCHMARK_REUSE.md): one developer, three matched synthetic pairs;
  raw median 95 s with Copilot versus 582 s manual, 83.7% lower. Complete outcomes were 3/3
  and 0/3 respectively; no both-correct V2 timing claim is made.
- [Release checks](PHASE6_RELEASE.md): 699 backend tests, 186 frontend tests, ten isolated
  PostgreSQL release journeys, three image scans, startup/restart and bounded restore/replacement.
- [AWS validation](../aws-live-validation/README.md): September infrastructure deployment and
  connected-service/recovery/teardown evidence; V2 was not newly deployed to AWS.
