# Evaluation V1 Methodology Audit

## Verdict

**Accept with explicit claim boundaries.** The evidence is useful for regression safety and portfolio depth. It is not sufficient for a general accuracy or customer-impact claim.

An independent post-execution reviewer initially returned **Needs revision** for overstated metric names, missing tested-source identity, and unsupported reviewer-provenance wording. After those issues were corrected, the reviewer returned **Accept with small fixes** for one remaining phase-table phrase; that phrase was then removed.

## What Is Strong

- Inputs and gold labels are separate, strictly validated, and frozen by SHA-256.
- Observation generation does not load labels; scoring happens afterward.
- Ten cases cover common, missing-information, conflicting-evidence, policy-heavy, noisy-evidence, and adversarial categories.
- Two repeats expose deterministic control drift.
- Control state, required evidence IDs, required retrieved policy ID/version/clause, four risk outcomes, escalation disposition, required and forbidden action types, unsupported claims, response safety, and schema validity are deterministic checks.
- A benchmark-discovered ownership-conflict defect was fixed in the product and protected by unit plus persisted integration regressions.
- The provider canary enforces a two-call ceiling, zero retries, complete usage records, measured cost, safety checks, and deterministic-control preservation.
- The persisted lane exercises critical stateful behavior that an engine-only benchmark cannot prove.

## Material Boundaries

1. The final 20/20 result is post-fix regression evidence. Because the suite informed the fix, it is now a development set rather than a blind holdout.
2. The aggregate does not score `expected_resolution` semantics. It scores control state and disposition; exact semantic fact phrasing, exact information-gap wording, and complete action-parameter equality are also outside the V1 pass gate.
3. Escalation accuracy means the decision correctly signaled an escalation disposition. It does not prove a ticket was routed to a specialist or supervisor.
4. Review submission and execution boundaries are validated by four targeted PostgreSQL scenarios, not all 20 benchmark observations.
5. The provider canary covers three cases and two paid calls. It checks integration and control preservation, not broad narrative quality.
6. P50/P95 values measure in-process deterministic engine execution only. They must not be presented as user-facing latency.
7. The suite is synthetic, small, and has provisional thresholds. Confidence intervals or population-level claims would be inappropriate.
8. No semantic LLM judge was used. This avoids judge bias but leaves response clarity and nuanced completeness unscored.
9. The embedded gold-label review-role fields do not have a separate pre-execution provenance artifact, so public claims do not describe the review as independently proven.
10. The frozen manifest records the benchmark freeze-point revision. The public deterministic result separately records a reproducible SHA-256 bundle fingerprint for the post-fix implementation that produced the final observations.

## Claim Review

| Candidate claim | Verdict |
| --- | --- |
| “20/20 synthetic regression observations passed implemented deterministic controls” | Supported |
| “100% accurate on customer cases” | Not supported |
| “OpenAI preserved server-owned controls in a bounded 3-case canary” | Supported |
| “The full workflow is production proven” | Not supported |
| “Critical review/action paths passed four guarded PostgreSQL scenarios” | Supported |
| “Automated decisions reduced human handling time” | Not established by this evaluation; use the separate matched workflow benchmark with its own limits |

## Recommended V2

Create a separate 20-30 case blind holdout after the product and grader are frozen. Canonicalize fact and information-gap identifiers, validate required action parameters, replay eligible cases through persisted review/action boundaries, and add a human-calibrated semantic rubric for response completeness. Keep V1 unchanged as the regression suite.
