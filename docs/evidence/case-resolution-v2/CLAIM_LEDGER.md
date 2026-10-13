# V2 claim-to-evidence ledger

2026-10-13: all new measurement claims are **not yet supported**. CV Goals stays unchanged.
The source spec table has five rows; the ledger separates operational cost/latency from
rollback/recovery into six independently checkable components.

| ID | Intended claim | Required artifact and metric | Owner phase | Current boundary |
| --- | --- | --- | --- | --- |
| C1 | Versioned Decision Brief, deterministic risk and human authority | Persisted input→policy/evidence→brief→bound approval→read-back trace; role/stale-payload negative tests | 1, 3, 4 | Phase 1 bounded lifecycle tests pass; real provider and full product evidence still pending |
| C2 | Median handling improvement X on N held-out controlled cases with Y policy correctness | Separate time-study protocol, raw timestamps, both-correct pairs, full-cohort quality and completion counts; exact medians/formula | 2, 4, 5 | Historical 83.7% cannot fill X; N pairs and full cohort must both be disclosed |
| C3 | Safe automation, actual escalation, reopen and verified actions | Operation/routing/ack/resolution-cycle events; all-case automation denominator; simulated 7/30d rates | 1, 4 | No automation claim from an approval-required workflow; no escalation claim from disposition |
| C4 | Policy correctness across N dated SOP revisions | At least 3 revisions, applicability interval, before/after/rollback cases, actual failure→fix→regression trace; counts per revision and aggregate | 2, 3, 4 | Versioned retrieval is not proof of policy application |
| C5 | p95 and cost per verified resolution | Stage traces with counts; timed profile; model usage/dated price sheet; measured costs divided by correct verified resolutions | 1, 4, 6, 7 | Engine milliseconds, tiny canary and cost/case cannot substitute |
| C6 | Rollback and uncertain-outcome recovery | Image/config/SOP identity, pending-operation snapshot, restart/read-back trace, effect count, restore evidence when required | 1, 3, 6, 7 | Runbooks describe intent; historical bounded checks do not prove complete live recovery |

Finalization requires exact numerator, denominator, date, source commit, environment and artifact
link per row. Mark unsupported claims with a truthful narrower alternative; never fill CV
placeholders from targets. Only a separate CV task may edit the final CV. No external testers,
customer adoption, production traffic or independent human review are presumed.

Phase 2 adds the [evaluator and frozen synthetic corpus](EVALUATOR.md). Its mutation tests validate
scorer sensitivity only. No product observations, holdout accuracy, independent human label review
or timing improvement are claimed. The quantitative claim boundaries above remain unchanged.
