# Case Resolution V2 — frozen measurement contract

Version: `case-resolution-v2-contract-1`. Frozen: 2026-10-13.
Status: Phase 0 design contract, **not an evaluation result**.

## Outcome boundary

A verified resolution requires policy-correct decisions, grounded required facts and gaps,
valid authority, exact consequential parameters, all required downstream read-backs, and a
persisted completion event. No unresolved obligation, unknown operation, or contradictory
evidence may remain. A saved reply draft is not delivered communication. Explanation-only
resolution requires evidence that no consequential action is owed and the required response
was delivered or explicitly attested by an authorized operator.

`policy_correct` is an all-or-nothing conjunction of semantic resolution predicates, required
facts/gaps, evidence grounding, applicable policy ID/version/clause/date, disposition,
consequential action parameters, authority boundary, and absence of forbidden actions/claims.
Schema validity and retrieval coverage are diagnostic components, never substitutes.

`correct_completion` additionally requires the oracle terminal outcome: either verified
resolution or safe escalation with the correct queue and authorized acknowledgement receipt.
Those two terminal types are reported separately. Escalation does not count as resolution,
safe automation, or a denominator for cost per verified resolution. An open case can be a
correct policy decision yet remain incomplete. `needs_review`, unavailable provider, timeout,
unknown result, and reopened state are never automatic success.

Completion is evaluated at the frozen scenario deadline (24 simulated hours by default).
Explicit delayed-event fixtures declare another deadline before sealing. Reopen is evaluated
separately at 7/30 simulated days; retain initial valid completion and subsequent invalidation
events. An initially invalid closure is a false closure, not a later legitimate reopen.

## Population and release gates

The machine-readable design is [measurement-contract.v1.json](../../../backend/evaluations/case_resolution_v2/measurement-contract.v1.json).
These are provisional engineering acceptance thresholds, not statistical population guarantees.

| Item | Frozen design |
| --- | --- |
| Final holdout | 40 new case families, one primary case per family; one primary run |
| Domain allocation | 14 billing, 13 refund, 13 account recovery families |
| Cross-cutting tags | At least 4 cases each: ambiguity, missing evidence, conflicting evidence, unauthorized actor, expired authority, stale SOP, duplicate action, timeout, reopen; tags may overlap |
| Critical subset | Every critical invariant below exercised; at least 12 unique holdout cases marked critical |
| Development | At least 24 new families; iteration permitted; never combined with holdout metrics |
| Regression | V1 unchanged, plus promoted development failures in a separate V2 manifest |
| SOP evolution | At least 3 meaningful dated revisions: refund eligibility, ownership conflict, escalation threshold; before/after/rollback cases for each |
| Time-study cohort | 12 new families (4/domain), disjoint from development/regression/holdout; at least 8 both-correct pairs needed for a timing claim |
| Policy correctness | At least 38/40 (95%) on scheduled primary holdout cases |
| Correct completion | At least 36/40 (90%); terminal types and failures separately reported |
| Critical gates | Zero unauthorized/duplicate effects, false closures, wrong consequential parameters/tenant, missed required escalation, or incorrect reopen behavior in required critical scenarios |
| Automation | No target percentage. Publish measured rate; zero eligible is N/A for eligible coverage |
| Timing improvement | No positive improvement requirement; publish zero/negative results if observed |

Final corpus counts and tag coverage are validated in Phase 2 before sealing. Extra diagnostic
variants and repeats never increase the 40 primary-family denominator. Increasing sample size
or changing thresholds requires a new pre-run contract version and rationale; no post-result
threshold tuning. Empty manifests now explicitly say `planned`; no holdout has been authored,
sealed, or executed by Phase 0.

## Metric rules

Every count carries run/cohort, case or operation IDs, environment, oracle version, time window,
numerator, denominator, and exclusions. Failures, invalid/missing observations, and provider
unavailability remain in the scheduled end-to-end denominator. Infrastructure abortion does
not permit silently dropping cases. Report planned/attempted/observed/scored counts together.

| Metric | Numerator / denominator |
| --- | --- |
| Policy correctness | All policy predicates pass / all scheduled unique cases |
| Correct completion | Correct oracle terminal reached with receipts / all scheduled unique cases |
| Safe automation | Correct verified resolutions without any human intervention / all scheduled cases |
| Eligible automation coverage | Correct automated resolutions / gold eligible cases |
| Actual escalation | Correct routing plus authorized acknowledgement by deadline / gold required escalations |
| Missed escalation | Required routing or acknowledgement missing by deadline / gold required escalations |
| Unexpected escalation | Incorrectly escalated cases / cases without gold escalation requirement |
| Verified action | Correct authorized operations with read-back / all gold-required operations plus unexpected observed operations |
| False closure | Invalid closures / all observed closures |
| Unsafe effect | Cases with unauthorized or duplicate effects / all scheduled cases |
| Missing observation | Cases without valid persisted observations / all scheduled cases |
| Reopen 7/30d | Unique initially verified closed cases reopened within window / initially verified closed cases with complete simulated follow-up |
| Reopen correctness | Expected invalidations that reopen exactly once, linked to original resolution / all expected invalidations |
| Provider cost per verified resolution | Provider USD spend on ALL attempts, including failed ones / correct verified resolutions |
| Total cost per verified resolution | Provider plus measured attributable runtime USD spend on ALL attempts / correct verified resolutions |

Zero denominator is `null` with display **N/A**, never 0% or 100%. Missing cost/usage gives
unavailable cost, not zero. Infrastructure estimates are separate from measured total cost.
Price snapshots include provider/model, date, currency, token categories and cache rates.
Retries contribute cost and latency but not extra successful cases. Count duplicate side
effects separately even when an operation eventually succeeds. Reopen cohorts with incomplete
follow-up are censored and reported explicitly. Duplicate reopen events count once per cycle.

For binary case-level rates report Wilson 95% intervals and raw counts; these describe the
synthetic sample, not real-world accuracy. Do not treat correlated repeats as independent samples.

## Latency and time study

Use monotonic duration clocks per process, UTC timestamps for event chronology, and stable
case/run/operation/correlation IDs. Capture intake, retrieval, decision, API request, queue
wait, worker attempt, provider request, DB, tool, human/approval wait, and end-to-end elapsed
separately. Child spans overlap: do not sum them as elapsed time. API starts at server ingress;
end-to-end starts at case intake and ends at verified completion/acknowledged escalation.
Unknown/pending cases have censored elapsed time, not a successful completion latency.

Report sample count, missing spans, timeouts, and successful/failed distributions separately.
p50/p90/p95 use nearest-rank `ceil(p*n)-1`; for fewer than 100 observations per stage, retain
raw/min/max/median and label p90/p95 insufficient for a headline latency claim. Phase 0 sets
measurement semantics, not a cloud latency SLA. Freeze workload-specific latency budgets in
the Phase 4 execution profile before running; cloud budgets belong to Phase 7.

The Phase 5 study uses the same oracle terminal and same required action/communication burden
in manual and assisted conditions. Both conditions' quality rates use all 12 assigned cohort
cases. Only both-correct pairs enter timing; report selected-pair N as well as full-cohort N,
failures and exclusions. At least 8 eligible pairs are required. Primary time is active handling;
wall-clock including approval/provider wait is secondary and separately labeled. Improvement
is `(median_manual - median_assisted) / median_manual * 100`. Also report median paired difference,
raw pairs, touches and corrections. A failed manual attempt is never a speedup pair.
Counterbalance order 6 manual-first/6 assisted-first; record operator learning and carryover.
No timing result is produced here. Single developer/operator is permitted and explicitly labeled.

## Oracle and split governance

Canonical models: [contracts.py](../../../backend/app/evaluation/case_resolution_v2/contracts.py).
Exported JSON schemas are in [the V2 evaluation directory](../../../backend/evaluations/case_resolution_v2/).
All family IDs represent underlying causal fact patterns, not a paraphrase or formatting variant.
SOP family means policy logic lineage, not just document ID. All revisions and paraphrases of
one SOP lineage stay in a single split. Author new, withheld SOP families for holdout/time study;
reusing a production policy at evaluation time is allowed, but tuning on that withheld family
before release-candidate freeze is not. Domain overlap across splits is intentional.

Hash input and label bytes independently. Labels specify exact action target/tenant and complete
consequential parameter maps, required facts/gaps, semantic resolution predicates, date basis,
policy versions, forbidden actions, escalation receipts, final state, and reopen expectations.
Billing maps must contain amount in integer minor units, currency, charge/order/customer/original
destination references. Recovery maps include account/identity target and allowed recovery scope.
No consequential key may be ignored by the Phase 2 scorer; extra consequential parameters fail.
Policy ambiguity uses expected conflicting sources and no authorized consequential action.

Oracle rationale comes from supplied facts and dated business rules, not product outputs.
Record developer adjudicator, timestamp, rule reference, and AI assistance truthfully. No claim
of independent human review unless evidence of that review actually exists. A second AI pass
does not constitute independent human review. Manual semantic family audit complements hash checks.

Phase 2 seals separate development/regression/holdout/time-study manifests with hashes, seed,
product revision, model/prompt/config/scorer versions. Keep private holdout input/labels under
ignored `backend/.benchmark-data/case_resolution_v2/`; publish a sanitized manifest only when
appropriate. Generation receives inputs only; labels become available to scoring only after
immutable observations and their digest are saved. If holdout is exposed for debugging, demote
it and create a new sealed corpus. V1 cases remain regression-only and are never recounted as new.

## Gate and phase boundary

Phase 0 passes when executable contracts reject contradictory authority/outcomes, bad policy
dates, insufficient seals, split leakage, invalid denominators, and mismatched timing outcomes;
all claim-ledger rows have evidence owners and planned tests. Schema tests cannot establish
policy quality, semantic family independence, actual read-back, or scorer sensitivity. Those
are later gates. Phase 0 adds no runtime behavior, no dataset results, no cloud resources and
no provider calls. See [audit](BASELINE_AND_ARCHITECTURE.md), [claim ledger](CLAIM_LEDGER.md),
and [test targets](TEST_TARGETS.md).
