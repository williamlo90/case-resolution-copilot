# Dated SOP changes and replay

Phase 3 adds executable, bounded constraints to governed SOPs and tests their interaction with
approval and uncertain actions. This is exposed synthetic regression evidence, separate from the
Phase 2 sealed holdout and from Phase 4 product evaluation.

## Contract

An immutable published source may include one fenced `case-resolution-rules` JSON block. Schema 1
supports `refund_window`, `ownership_proof`, and `escalation_threshold`. Unknown fields, malformed
rules, duplicate rule kinds, unsupported categories and ambiguous authority fail closed. Only an
authorized policy manager can publish through the existing governed API. Source content stays
immutable; lifecycle metadata records publication, retirement and effective intervals.

The deterministic engine is now `deterministic-decision-engine-v4`, prompt `decision-brief-rules-v3`,
with risk/control identity `generic-risk-rules-v3`.
These controls supplement existing source freshness, delivery, duplicate payment and identity checks.
They cannot bypass those checks. Prose-only policies retain the existing bounded behavior; arbitrary
natural language is **not** converted into executable business logic. Money thresholds in schema 1
accept USD cents only; other policy currencies are rejected. No FX conversion is performed.

Selection uses decision/retrieval time, with inclusive start and exclusive end. Refund age separately
uses purchase time to request-received time, inclusive of the exact allowed duration. Request-time or
transaction-time policy selection is not added to the operational API by this phase.

## Frozen synthetic timeline

| Rule family | v1: Oct 1–8, 2026 | v2: Oct 8–12, 2026 | v3: from Oct 12, 2026 |
| --- | --- | --- | --- |
| Refund | Maximum 7 days | Maximum 14 days | Restore 7 days |
| Ownership | Verified proof | Independent verified proof | Restore verified proof |
| Monetary escalation | Above USD 100 requires review | Above USD 50 requires review | Restore USD 100 |

Each family has one decision-changing case and one unaffected control. Six new exposed inputs are
observed at three dates: Oct 2, Oct 9 and Oct 13. The schedule contains 18 observations, including
rollback. The nine immutable source versions, input/label hashes, publisher identities, rationale
and labels live in `backend/evaluations/sop_revisions/`. Authoring/adjudication is by the Codex agent,
not independent human review. Dates are simulated policy dates, not historical production usage.

The replay calls the real deterministic decision engine with frozen source retrieval snapshots.
It checks disposition/state, exact action type and parameters, money, review boundary, blocking SOP
reason and deterministic output. It does not execute payments or establish correct completion.
SQL retrieval and API publication/approval/recovery are exercised separately by integration tests.

## Approval and recovery controls

- Retrieval, approval freshness and action authorization share the same effective-version selector.
  Drafting a replacement leaves the previous published version authoritative. A scheduled version
  supersedes it only when its effective interval begins.
- Publication, approval and dispatch preparation serialize on a tenant-scoped PostgreSQL transaction
  lock. The dispatch lease is the authorization boundary. A lease committed before publication may
  already be in flight; later publication does not revoke an external effect. Provider calls run
  outside the database lock. Later dispatch must pass the new authority check.
- An approval tied to a replaced version is stale. Restoring old content in a **new** version does
  not revive old approvals. Reopen investigation, regenerate and obtain fresh review.
- Running, unknown, recovery-required or completed effects block another action of the same type
  and target in the same case, including actions from a new proposal. Terminal-absence proof is
  needed before a safe retry. Additional intentional effects require a separately governed case.
- Read-only reconciliation still uses the original operation identity after policy rollback and
  service reconstruction. It does not generate a fresh action or invoke the decision model.

## Actual failure promoted to regression

On 2026-10-14, the initial development test
`test_refund_window_is_enforced_from_published_source` failed against the Phase 2 engine at
`d3ea59509c1b4c6f594cceee72b6a30c565aa795`:

```text
assert not any(action.type == "issue_refund" for action in result.proposed_actions)
E   assert not True
1 failed
```

Source: published seven-day refund rule. Evidence: unused order purchased Jan 1, request in July.
Actual: `issue_refund` proposal. Expected: no refund proposal; blocking SOP review. Severity: high,
incorrect consequential proposal; no payment was executed. Root cause: the engine checked delivery
and evidence relevance but never interpreted the rule in the retrieved source. Fix: explicit typed
SOP predicates run before proposal state and actions are constructed. The regression now requires
both suppression of the refund and the specific `refund_window` reason, avoiding a vacuous pass
from an unrelated configuration error. The single Phase 3 checkpoint commit contains the fix.

## Reproduction and results

Use the [SOP revision gate](https://github.com/williamlo90/case-resolution-copilot/actions/workflows/sop-revision-gate.yml)
for the exact checkpoint SHA. It runs bounded unit tests, disposable PostgreSQL API journeys,
concurrent publication versus approval, and the full deterministic replay on GitHub Actions.
No external model/payment credentials are used. CI has a 15-minute timeout and one job.

The artifact `phase3-evidence-<commit>` contains:

- `config.json`: exact commit, model/prompt/graph/rules, environment, date, seed and fixture manifest;
- `observations.json`: saved before oracle access, including failed observations;
- `report.json`: observation hash, per-family/per-revision numerator/denominator, aggregate and traces;
- unit/integration JUnit results, including the concurrency gate.

Full replay refuses local execution. The 18 scheduled observations remain in the denominator on
engine failure. Run directories cannot be overwritten. Download the artifact for durable retention;
GitHub's hosted artifact retention is 30 days. Use the checkpoint source and frozen fixtures to
reproduce after expiration. No holdout, production correctness percentage, speedup, provider uptime,
or deployment rollback claim follows from this development replay.

SOP content rollback and pending-operation resume are covered here. Actual old-image/schema rollback
and live provider/config recovery remain release gates in Phases 4 and 6.
