# V2 release readiness

This tracker applies to the V2 release candidate. The current evidence supports a synthetic, controlled demo. Phase 6 packaging is complete; the existing Vercel/Neon/Clerk demo remains available. See [release evidence](../evidence/case-resolution-v2/PHASE6_RELEASE.md). Production activation still requires the open gates below.

| Gate | Required evidence |
| --- | --- |
| Container security — passed for validated candidate | Backend, frontend, and PostgreSQL reports recorded zero HIGH/CRITICAL findings in the candidate run; scan results are specific to those image identities. |
| Container behavior — passed for validated candidate | Isolated build, migrate/seed, API/UI route smoke, restart and logical restore passed. The restore fixture has no action/receipt/resolution rows; this is not a populated workflow restore or application cutover. |
| Application rollback | Previous known-good images/config verified against the current schema, followed by readiness and affected workflow checks. |
| Restore cutover | Isolated restore integrity plus application reconnection and affected tenant/workflow checks; record actual recovery duration and data-loss boundary. |
| Real provider boundary | Bounded provider activation and read-back evidence for each external target being claimed. Synthetic target evidence remains labelled synthetic. |
| Cloud reliability | Phase 7 workload, fault lifetime, queue/DLQ isolation, identities/alerts, restore integrity, stop/teardown evidence, and cost record. |
| Optional new V2 timing claim | Phase 5 is complete through historical benchmark reuse. A new V2 time-saving claim would require a separate same-outcome operator study; this is not a release blocker. |

Source validation, dependency audits, and database integration are necessary inputs, but do not close an image or live reliability gate. The [Phase 6 runbook](../runbooks/PHASE6_DEMO_RELEASE.md) defines the bounded demo and recovery checks. The [isolated workflow](../../.github/workflows/phase6-demo-smoke.yml) retains image scan reports and database test artifacts; its actual result governs release status.
