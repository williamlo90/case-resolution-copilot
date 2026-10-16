# V2 release readiness

This tracker applies to the V2 release candidate. The current evidence supports a synthetic, controlled demo. Production activation requires the open gates below.

| Gate | Required evidence |
| --- | --- |
| Container security | Backend, frontend, and PostgreSQL image reports tied to immutable image identities; no unresolved HIGH/CRITICAL findings. |
| Container behavior | Isolated build, migrate/seed, API and UI smoke, restart, and disposable logical restore checks on the release candidate. |
| Application rollback | Previous known-good images/config verified against the current schema, followed by readiness and affected workflow checks. |
| Restore cutover | Isolated restore integrity plus application reconnection and affected tenant/workflow checks; record actual recovery duration and data-loss boundary. |
| Real provider boundary | Bounded provider activation and read-back evidence for each external target being claimed. Synthetic target evidence remains labelled synthetic. |
| Cloud reliability | Phase 7 workload, fault lifetime, queue/DLQ isolation, identities/alerts, restore integrity, stop/teardown evidence, and cost record. |
| Human time study | Phase 5 operator attempts and same-outcome scoring before any new time-saving claim. |

Source validation, dependency audits, and database integration are necessary inputs, but do not close an image or live reliability gate. The [Phase 6 runbook](../runbooks/PHASE6_DEMO_RELEASE.md) defines the bounded demo and recovery checks. The [isolated workflow](../../.github/workflows/phase6-demo-smoke.yml) retains image scan reports and database test artifacts; its actual result governs release status.
