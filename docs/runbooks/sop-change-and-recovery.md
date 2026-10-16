# SOP change, regression and rollback

## Publish a change

1. Record the proposed rule, decision-time effective interval, affected categories, authorized
   publisher, and expected before/after decisions. Use exposed development inputs only.
2. Create a new draft with `POST /api/policies/{id}/versions`, using the current policy version.
   Include the prose and explicit `case-resolution-rules` block. Supported schema is documented in
   [SOP revisions](../evidence/case-resolution-v2/SOP_REVISIONS.md).
3. Submit review with `POST /api/policies/{id}/versions/{version}/submit-review`. Publish or schedule
   using the resulting policy and record versions. A specialist cannot publish. Never edit an
   already-published source or mutate version IDs in SQL.
4. Run the exposed revision gate on the proposed commit. Verify source hash, date boundaries,
   changed case and unaffected control, amount/target, stale approval and rollback behavior.
5. Record the release commit, policy version/content hash, model/prompt/graph identity, retrieval
   profile, fixture manifest hash, run ID and report. A successful syntax check alone is not a gate.

## Handle an invalidated approval

1. Read action details. `stale_proposal` means the old approval cannot dispatch.
2. If there is any running/unknown/prior completed effect, follow recovery below first. Do not
   bypass it by creating a new proposal, operation key or case just to retry.
3. Move the case back to `investigating` with its current case version. Generate a new proposal
   via `POST /api/cases/{id}/proposals`; inspect its exact policy/evidence and action parameters.
4. Submit the new proposal version for review, reserve it, and have an authorized reviewer approve
   the new snapshot fingerprint. The previous approval and audit remain intact.
5. Execute only an eligible new action. Approval expiry, changed evidence and target-effect guards
   still apply. A recommendation to escalate must be routed and acknowledged using the Phase 1
   resolution API before it counts as actual escalation.

## Triage a failed decision and promote a regression

Capture sanitized input, applicable source/version/interval, retrieved clause, observed decision,
action parameters, expected oracle, severity and exact config/commit. Determine whether the cause
is missing evidence, incorrect retrieval, rule parsing, decision logic, approval or target read-back.
Add an exposed regression with an independent expected outcome, reproduce the failure, implement the
fix, and record post-fix result plus fix commit. Keep output observations before reading the oracle.
Do not tune against the sealed Phase 2 holdout. If it becomes debugging input, demote it and create
a new holdout before any new blind-test claim.

## Roll back an SOP

Copy the known-good source into a **new** version, with a new effective start. Submit and publish
through the same authorization path. Record which version it restores in the change record; confirm
equal content hashes and different immutable version IDs. Do not restore old version pointers or
erase newer audit events. Old approvals stay stale and require reevaluation/reapproval.

For a scheduled change that has not taken effect, use the existing retire command and confirm the
previous active version remains selected. Never backdate a replacement before the start of the
version it replaces; conflicting/invalid intervals require a corrected forward version.

## Recover an unknown outcome

Read the original action, attempts and receipt. Save its action ID and operation/idempotency identity.
`POST /api/actions/{id}/reconcile` performs lookup; it must not resend the command. If completed,
verify amount, currency, target and immutable receipt. If unknown, keep it unknown and escalate.
Retry only after the target proves terminal absence and the current approval remains valid.

After rollback/restart, use the same persisted action and target receipt store. Never reset the
database, wipe attempts, or generate a replacement idempotency key. A completed operation can be
known to have happened even when its old policy approval no longer permits case closure. Reevaluate
the case separately; do not repeat the effect.

Model/prompt/config rollback must retain these persistence and gateway contracts. Do not deploy an
older engine that ignores executable SOP blocks while those policies remain active. A deterministic
target retained across service reconstruction tests the application recovery contract; durable real
provider behavior and image/schema rollback need the separate Phase 4/6 gates.

## Reproduce safely

Run `pytest tests/unit/test_sop_revision_decisions.py -q` locally. PostgreSQL journeys use the
guarded disposable-database runner. Full replay and `PHASE3_CONCURRENCY=1` belong only in the
`SOP revision gate` isolated workflow. No local browser, load test or replay loop is needed.
