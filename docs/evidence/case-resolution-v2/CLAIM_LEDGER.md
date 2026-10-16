# V2 claim-to-evidence ledger

2026-10-16: Phase 5 is complete through [historical benchmark reuse](PHASE5_BENCHMARK_REUSE.md).
The original timing result retains its decision-workflow scope. New V2 timing and production
claims are not established by that result; V2 quality evidence remains separate. CV Goals stays unchanged.
The source spec table has five rows; the ledger separates operational cost/latency from
rollback/recovery into six independently checkable components.

| ID | Intended claim | Required artifact and metric | Owner phase | Current boundary |
| --- | --- | --- | --- | --- |
| C1 | Versioned Decision Brief, deterministic risk and human authority | Persisted input→policy/evidence→brief→bound approval→read-back trace; role/stale-payload negative tests | 1, 3, 4 | Phase 1 bounded lifecycle tests pass; real provider and full product evidence still pending |
| C2 | Historical decision-workflow timing: 95 s Copilot vs 582 s manual; 83.7% lower raw median | Original report, protocol, raw results and persisted state; one operator, three synthetic cases per condition | 5, revised scope | Complete under benchmark reuse: 3/3 Copilot vs 0/3 manual complete outcomes. Not a both-correct V2 resolution speedup; do not combine with V2 holdout quality |
| C3 | Safe automation, actual escalation, reopen and verified actions | Operation/routing/ack/resolution-cycle events; all-case automation denominator; simulated 7/30d rates | 1, 4 | No automation claim from an approval-required workflow; no escalation claim from disposition |
| C4 | Policy correctness across N dated SOP revisions | At least 3 revisions, applicability interval, before/after/rollback cases, actual failure→fix→regression trace; counts per revision and aggregate | 2, 3, 4 | [Phase 3](SOP_REVISIONS.md) supplies exposed deterministic replay; exact-commit CI artifact supplies counts. No holdout or end-to-end completion claim |
| C5 | p95 and cost per verified resolution | Stage traces with counts; timed profile; model usage/dated price sheet; measured costs divided by correct verified resolutions | 1, 4, 6, 7 | Engine milliseconds, tiny canary and cost/case cannot substitute |
| C6 | Rollback and uncertain-outcome recovery | Image/config/SOP identity, pending-operation snapshot, restart/read-back trace, effect count, restore evidence when required | 1, 3, 6, 7 | [Phase 6](PHASE6_RELEASE.md) validates known-good image/config replacement, seeded logical restore, and persisted unknown-outcome retry blocking after application recreation. Previous-release binary compatibility, populated action-ledger restore/cutover and real-provider recovery remain separate gates |

Finalization requires exact numerator, denominator, date, source commit, environment and artifact
link per row. Mark unsupported claims with a truthful narrower alternative; never fill CV
placeholders from targets. Only a separate CV task may edit the final CV. No external testers,
customer adoption, production traffic or independent human review are presumed.

Phase 2 adds the [evaluator and frozen synthetic corpus](EVALUATOR.md). Its mutation tests validate
scorer sensitivity only. No product observations, holdout accuracy, independent human label review
or timing improvement were claimed at that checkpoint. Phase 5 now reuses the historical
decision-workflow benchmark under the scope documented above.
