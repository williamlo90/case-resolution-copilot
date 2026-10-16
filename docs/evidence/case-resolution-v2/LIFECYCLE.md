# Verified lifecycle and operator runbook

Phase 1 adds operational evidence. These counters are not oracle-scored V2 evaluation results.
The frozen measurement contract and V1 evidence remain unchanged.

## Supported flow

1. Generate a decision brief from current evidence and policy; reserve and approve its immutable review.
2. Execute the materialized action using its current version. The persisted operation ID is reused
   for lookup; an HTTP acknowledgement leaves the action `outcome_unknown`.
3. Reconcile with `POST /api/actions/{id}/reconcile`. A matching, recent target read-back is required
   to mark the action completed. The receipt alone, or a manual completion note, cannot do so.
4. Read `GET /api/cases/{id}/resolution`, then submit a lifecycle command with that case version.
   A supervisor/administrator closes the case only after all actions have current verification and
   supplies a delivered-message reference as an explicit operator attestation.
5. New evidence reopens the same case, linking a new event to the preceding completion. A later
   failed/unknown target check also reopens a closed case without sending another write.
6. Route an escalation to an active same-tenant supervisor/administrator. This updates the actual
   case owner; the `supervisor_review` destination is recorded in the event. Only that recipient
   can acknowledge the latest routing event. Recommendation, routing, acknowledgement and closure
   remain different events; acknowledgement does not mark the case resolved.

The lifecycle command endpoint is API-first. Existing action UI exposes target lookup and manual
notes; manual notes cannot select completion. A dedicated lifecycle workspace UI is not included.
Explanation-only closure and autonomous action grants are disabled. Cases without verified actions
remain open or use acknowledged escalation. Gmail draft creation never proves message delivery.

## Command contract

`POST /api/cases/{case_id}/resolution` accepts:

```json
{
  "expected_version": 3,
  "command_id": "unique-command-key-0001",
  "kind": "completed",
  "reason": "Verified target outcome and customer communication",
  "reference": "delivered-message-reference"
}
```

Kinds: `completed`, `reopened`, `escalation_routed`, `escalation_acknowledged`.
Reference respectively identifies delivered communication, new evidence, recipient membership
public ID, or routing event UUID. Evidence/message references are operator attestations, not
independently fetched documents. Same actor/key/payload replays the same event even after the case
version advances. Changed replay payload, stale version or invalid transition yields 409;
insufficient role yields 403; another tenant's case yields 404.

Events retain timestamp, actor, correlation ID, case version, previous event and command identity.
Tenant/case foreign keys prevent cross-case history links. Commands lock the case before actions.
Events are append-only through application commands and mirrored into the existing audit stream;
a database administrator is still capable of modifying records. Migration 0025 adds the ledger
without manufacturing verification for legacy completed cases. Downgrade requires exporting the
ledger first; rollback removes the new table and cannot preserve its evidence by itself.

## Read-back and recovery

Signed webhook reconciliation may return `readback` with operation ID, external reference,
action type, target, all observed parameters, amount/currency, effect count, status and an aware
observation timestamp. Execution requests now include amount/currency separately from parameters.
Only exact matches, one effect, `verified`, and an observation no older than five minutes pass.
Future timestamps fail closed. Missing proof on an older adapter remains unknown.

Before dispatch, authorization checks current case/proposal/review, expiry, exact payload and
amount, current policy version/effective interval and bound evidence/context. Before closure,
authority and evidence are checked again, verification must match the current case version and
payload, and no target check may be running. Reopen or later observations supersede old proofs.
All materialized actions currently count as obligations; failed/superseded actions are not silently
excluded. Multi-action cancellation/supersession needs an explicit future contract.

An abandoned read-only lookup can be resumed after its five-minute lease expires.
After timeout, reconcile the same operation; never invent a new operation ID to bypass uncertainty.
Only authoritative terminal absence can permit a safe retry, subject to all existing blockers.
If the provider is unavailable, preserve unknown and escalate. A completed action may be checked
again. Reopen detection is triggered by this lookup; no background polling is introduced.

The deterministic demo adapter stores effects in memory and is only a test double. Restarting it
loses lookup knowledge, which yields unknown rather than success. A production adapter must use a
durable provider ledger; this checkpoint does not validate a real refund provider.

## Telemetry and operational metrics

Structured `case.lifecycle_stage` records require correlation ID, subject ID, stage, nonnegative
finite duration and outcome. No customer payload is included. Existing request middleware records
API duration. New spans cover retrieval/decision, narrative provider, action DB/tool/verification,
inbox queue wait/worker/provider/intake/DB, and review wait. Routing acknowledgement persists
manual wait; closure persists elapsed time since case creation. Nested spans overlap and must not
be summed. Queue wait is from job availability to claim processing, including scheduler delay.
A completed timing span means the code block returned, not that the business outcome was verified.
Join spans through subject IDs and persisted review/action/case lineage; each request has its own
correlation ID. There is no p95 claim from these small tests.

Quality reports expose distinct reopened cases, verified actions, routed/acknowledged event counts
and rates. Rechecking one action does not increase the verified-action numerator. Legacy status
counts remain separate from the verified-action metric. Automation is disabled: zero automated
resolutions across cases and zero eligible cases (eligible coverage displays N/A). Denominator-zero
rates display N/A. These are tenant-wide operational counts, not simulated 7/30-day reopen cohorts,
policy correctness or holdout completion rates; Phase 2/4 own those evaluators.

## Bounded validation

Run targeted unit tests and `backend/scripts/run_integration_tests.ps1` with an ignored disposable
Neon configuration. The runner verifies the disposable marker, endpoint identity and TLS before
resetting its test database and redacts credentials. Never point it at application data.
The integration suite rehearses the additive migration, denied/stale authority, accepted/unknown
outcomes, read-back, completion/reopen and actual routing acknowledgement. Heavy concurrency,
browser E2E, production migrations and paid provider calls are outside this checkpoint.
