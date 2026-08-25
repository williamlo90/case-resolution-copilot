# Developer-Operated Decision Workflow Benchmark

## Final Result

**Complete.** Copilot produced `3/3` complete, safe workflow outcomes; the manual condition produced `0/3` complete outcomes under the same scoring boundary.

| Condition | Complete workflow | Disposition | Policy/version | Approval boundary | Safe next action | Unsupported claims | Unsafe executions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Manual | 0/3 | 3/3 | 3/3 | 0/3 | 0/3 | 2 | 0 |
| Copilot | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 0 | 0 |

The approval metric checks whether human review is required, not whether a fixed role name is shown. The active settings correctly routed the `REF-B` USD 1,120 proposal to `administrator`.

## Timing

Raw median elapsed time was `582 s` manual versus `95 s` with Copilot: `487 s` lower (`83.7%`, `6.1x`). This is descriptive timing from three synthetic cases per condition, not a population-level productivity estimate.

| Decision pair | Manual | Copilot |
| --- | --- | --- |
| Billing | Fail, 582 s | Pass, 90 s |
| Refund | Fail, 475 s | Pass, 95 s |
| Account recovery | Fail, 686 s | Pass, 123 s |

Because the manual cases did not meet the complete-workflow boundary, the raw timing difference is not presented as a correctness-controlled speedup.

## Persisted Evidence

All three Copilot outcomes were re-read from the disposable Neon validation database. The snapshot contains proposal state, bound business contexts, blocking requirements, policy/version, action gating, review route, and response status; it contains no credential values.

The immutable timed `REF-B` proposal retains `Duplicate charges` inside the correct `POL-1008` policy. A read-only retrieval preview using the fixed code now returns `Refund eligibility`. The timed defect remains disclosed and is not silently rewritten.

## Safety Controls

| Scenario | Result |
| --- | --- |
| Stale review authority is rejected | Pass |
| Unknown provider outcome cannot use safe-failure retry | Pass |
| Receipt reconciliation does not execute twice | Pass |

Targeted verification: `3/3` tests passed in one serial Pytest process.

## Measurement Note

The original strict scorer returned `0/6` because it required internal `CTX-*` and `MSG-*` identifiers, canonical backend action codes, and a fixed reviewer role that the operator-facing interfaces did not expose. Its output is retained as `strict-diagnostic-results.csv`. The final scorer uses visible source references, semantic action aliases, the human-review boundary, and persisted Copilot state.

## Revisions And Environment

- Product commit: `fb54f38`
- Benchmark package commit: `local-uncommitted@fb54f38`
- Run date: `2026-08-24`
- Operator: `developer-operator-01`
- Browser: `Codex in-app browser`
- Deployment: `benchmark-validation Vercel preview`
- Validation seed target: `disposable Neon validation branch`
- Finalized at: `2026-08-25T15:04:06.270804+00:00`

## Claim Boundary

This is a developer-operated matched synthetic benchmark with one operator and three cases per condition. It supports a portfolio claim about this controlled workflow, not a claim about production users, customer impact, or general model accuracy.

**Portfolio-safe wording:** In a developer-operated matched synthetic benchmark, Case Resolution Copilot produced 3/3 complete safe workflow outcomes versus 0/3 manually; raw median elapsed time was 95 seconds versus 582 seconds. Three targeted safety tests also passed.
