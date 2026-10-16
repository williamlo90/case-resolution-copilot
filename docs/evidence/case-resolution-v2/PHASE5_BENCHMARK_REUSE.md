# Phase 5 — workflow benchmark

Status: **complete under the revised scope approved by the project owner on October 16, 2026**.
Phase 5 uses the completed decision-workflow benchmark. V2 engineering updates are documented
separately; a new operator timing study is optional future work and does not block Phase 6.

## Measured result

| Measure | Manual | Copilot |
| --- | ---: | ---: |
| Synthetic cases | 3 | 3 |
| Complete workflow outcomes | 0/3 | 3/3 |
| Raw median elapsed time | 582 s | 95 s |

The raw median difference is 487 seconds, or 83.7% lower elapsed time with Copilot:
`(582 - 95) / 582 * 100 = 83.6769759...%`.

The [original report](../developer-workflow-benchmark/REPORT.md),
[protocol](../developer-workflow-benchmark/PROTOCOL.md),
[raw results](../developer-workflow-benchmark/raw-results.csv), and
[persisted state snapshot](../developer-workflow-benchmark/copilot-state-snapshot.json)
remain the source evidence. The run occurred on August 24, 2026, with one developer operator,
product revision `fb54f38`, a Vercel preview, and a disposable Neon validation branch.
It covered billing, refund, and account recovery with three matched synthetic case pairs.

The timed task ended at an accepted next disposition: ready for review, information needed,
or escalation. Because no manual outcome passed the complete-workflow criteria, this result
does not measure speedup between equally successful resolutions. It does not measure handling
time for V2 target read-back, acknowledged escalation, or verified case closure.

## Documentation decision

The README retains the measured timing and outcome counts with their original scope. V2 lifecycle,
dated SOP, and controlled-operation updates are described separately. No V2 quality score or
holdout count is combined with the historical timing cohort into a new performance claim.

No new operator study was run. Its draft instruments are retained locally in an ignored archive.
The frozen V2 measurement contracts and evaluation inputs remain unchanged; their same-outcome
requirements still apply if a new V2 timing claim is pursued later. This scope decision supersedes
earlier roadmap statements requiring a new study to close Phase 5.

## Checkpoint gate

- Historical medians, raw timing difference, and completion counts reproduce from the raw results.
- README and claim ledger identify the original measurement scope.
- Documentation links and diff whitespace checks pass.
- One documentation commit records Phase 5; implementation-plan copies stay local and ignored.

See the [learning checkpoint](../../learning/case-resolution-v2/PHASE-5.md).
