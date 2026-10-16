# V2 claim to evidence ledger

Final documentation audit: October 16, 2026. Application quality, exposed SOP regression,
historical operator timing, container validation and AWS architecture evidence are separate lanes.
The actual CV and its goals document are unchanged; use the
[application pack](../../portfolio/APPLICATION_PACK.md) for a later CV task.

| ID | Supported statement | Exact evidence | Boundary |
| --- | --- | --- | --- |
| C1 | Governed decisions and correct terminal outcomes on 40/40 held-out synthetic cases | [Results](RESULTS.md), [aggregate](results/phase4-holdout.json); Oct 14, source `1463826`; [CI 38513662226](https://github.com/williamlo90/case-resolution-copilot/actions/runs/38513662226) | Actual PostgreSQL-backed APIs, deterministic decisions/targets, agent-reviewed labels; not general LLM accuracy or client outcomes |
| C2 | Historical raw median workflow time 95 s Copilot vs 582 s manual, 83.7% lower | [Original report](../developer-workflow-benchmark/REPORT.md); Aug 24, product `fb54f38`, one operator, three synthetic pairs | Complete outcomes 3/3 vs 0/3; no same-outcome V2 speedup; do not combine with the 40-case quality cohort |
| C3 | 19/19 verified actions, 21/21 required acknowledged escalations, four duplicate dispatches blocked | [Holdout aggregate](results/phase4-holdout.json); Oct 14, source `1463826` | All consequential actions approval-required; no hands-free automation claim. Day-7/day-30 reopen 4/4 each is simulated replay, not a production rate |
| C4 | 18/18 exposed decision observations across six cases, three SOP families and three dated versions per family | [Replay aggregate](results/sop-replay.json); Oct 14, source `2f08942`; [CI 38507144879](https://github.com/williamlo90/case-resolution-copilot/actions/runs/38507144879) | Nine source versions, 2/2 per family/version; decision regression, not completion or holdout. [Failure/fix trace](SOP_REVISIONS.md) retained |
| C5 | API p95 100.8 ms from 468 samples in synthetic CI | [Holdout aggregate](results/phase4-holdout.json); Oct 14, source `1463826` | No cloud/API SLA, end-to-end p95, worker/provider percentile, or combined cost per resolution claim. Provider calls/cost zero in deterministic lane; infrastructure cost unmeasured |
| C6 | Known-good image/config replacement, seeded logical restore and persisted unknown-outcome safety | [Phase 6 evidence](PHASE6_RELEASE.md); Oct 16, candidate `5dbbbdb`; [CI 38901537078](https://github.com/williamlo90/case-resolution-copilot/actions/runs/38901537078) | Ten PostgreSQL journeys passed; empty action ledger in restore fixture. Previous-binary compatibility, populated restore/cutover, real-provider recovery and RTO/RPO remain separate gates |

## Deployment and review status

The existing hosted demo remains Vercel/Neon/Clerk at the revision documented in the
[release check](PHASE6_RELEASE.md). V2 source and container validation do not imply hosted promotion.
The [AWS architecture validation](../aws-live-validation/README.md) remains dated September 25
at source `0a92c4b`; no new V2 AWS deployment/load claim is made. Phase 7 live execution was
omitted after the scope audit because it was unnecessary for the selected claims.

The [evidence index](README.md) provides the reviewer path. Frozen contracts, original reports,
labels and observations retain their original meaning; new wording does not change measured data.
No production traffic, external testers, independent human adjudication, or client adoption is presumed.
