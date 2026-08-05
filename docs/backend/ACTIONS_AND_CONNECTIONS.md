# Controlled Actions And Connections

Status: Implemented in Backend Sprint B6
Date: 23 July 2026

## Purpose

An approved resolution may authorize a business change, but approval never performs the change.
B6 creates a separate controlled action that a permitted human can inspect and execute.

The operator language stays direct:

- `Execute action`
- `Retry safely`
- `Check target`
- `Record outcome`
- `Escalate for recovery`

The service keeps fingerprints, idempotency, and side-effect state in the audit boundary without
making those terms the primary UI instruction.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/actions` | Read the tenant action queue |
| `GET` | `/api/actions/{action_id}` | Read approval, target, attempt, receipt, and recovery detail |
| `POST` | `/api/actions/{action_id}/execute` | Execute one ready approved action |
| `POST` | `/api/actions/{action_id}/retry` | Retry only after proof that no target change occurred |
| `POST` | `/api/actions/{action_id}/reconcile` | Check the target without issuing another write |
| `POST` | `/api/actions/{action_id}/manual-outcome` | Record a human-verified unknown outcome |
| `POST` | `/api/actions/{action_id}/escalate` | Assign uncertain or failed work for manual recovery |
| `GET` | `/api/connections` | Read secret-free connection capability and health |
| `GET` | `/api/connections/{connection_id}` | Read one secret-free connection |
| `POST` | `/api/connections/{connection_id}/test` | Record a read-only health-check receipt |

Reads require `action:read` or `connection:read`. Execution requires `action:execute`.
Reconciliation, manual outcome, and recovery escalation require `action:reconcile`. Connection tests
require `connection:manage`. The authenticated actor owns tenant and role scope; client role headers
do not grant authority.

## Approval To Action Boundary

An `approve` review decision creates an action in the same database transaction. It does not call a
provider. The action binds:

- exact case, proposal, proposal version, and proposed action;
- exact review, immutable review snapshot, and approval decision;
- server-generated idempotency key;
- typed parameters, target, expected outcome, and impact;
- selected target connection;
- approval expiry;
- whether the reviewed snapshot can authorize execution.

Execution is allowed only while the case and proposal still match the reviewed snapshot, the
approval is unexpired, the target is configured with a healthy check no older than 15 minutes, no
receipt exists, and the actor has permission. Any failed check stops before an attempt is created.

## States

| Stored state | Plain meaning | Allowed next step |
| --- | --- | --- |
| `ready` | Approved and waiting for a permitted human | Execute |
| `running` | One target call has a durable attempt lease | Wait; abandoned leases become unknown |
| `completed` | A target receipt or human-verified outcome confirms completion | No further write |
| `failed_safe` | Evidence proves the target was not changed | Retry safely or escalate |
| `outcome_unknown` | A change may have occurred but cannot yet be proved | Check target, record outcome, or escalate |
| `recovery_required` | A human owns manual recovery | Check target or record outcome |

`failed_safe` and `outcome_unknown` are intentionally different. Unknown outcomes never expose
`retry_safe`. A running attempt left unfinished for five minutes becomes `outcome_unknown`; the
system does not assume that a process crash means no side effect.

## Transaction And Idempotency

Execution uses three bounded phases:

1. lock and validate the action, then commit a running attempt;
2. call the selected adapter outside a database transaction;
3. lock the attempt and store its safe failure, unknown result, or durable receipt.

The target call uses one server-owned idempotency key. Repeating the same deterministic demo request
returns the same external reference and marks the receipt as duplicate. A second product execution
is still rejected once a receipt is bound.

Unexpected adapter exceptions are recorded as `outcome_unknown` with possible side effect. They are
not silently converted to a safe failure.

## Reconciliation And Recovery

Reconciliation is read-only. It uses the recorded action identity and idempotency key:

- a found target change stores the returned receipt and completes the action;
- only explicit terminal absence evidence moves the action to `failed_safe`, enabling a controlled
  retry;
- an unavailable, ambiguous, or eventually consistent miss keeps the action `outcome_unknown`.

A manual `not_completed` note records the operator's observation but does not prove terminal
absence and never unlocks retry. Manual completion evidence can close the action; otherwise the
operator must reconcile again or escalate.

A supervisor or administrator may record a manual outcome with a reason. That creates an
attributable reconciliation record; it does not fabricate a provider receipt. Escalation assigns
the recovery work and keeps the original attempts intact.

## Connections

Connection records contain:

- provider type and internal adapter key;
- demo, sandbox, or production environment;
- health and last checked time;
- credential status only, never a credential value;
- read/write capabilities, supported action types, and affected work.

There are no API key, token, password, client-secret, or credential payload columns. The B6
deterministic adapter performs bounded in-memory behavior and requires no `.env`.

Run `scripts/seed_connections.py` only after a database is configured. It is disabled in production.
If an approved action has no matching connection, the system creates a visible
`not_configured` placeholder and blocks execution instead of dropping the action or guessing a
provider.

## Migration And Verification

Alembic creates action, attempt, receipt, and connection records directly. The reconstructed runtime
ships no legacy action mapper and never replays historical provider writes. Gateway, idempotency,
unknown-outcome, reconciliation, authority, and route tests run in the serial release gate.
PostgreSQL row locking and uniqueness behavior still requires the guarded disposable-database suite;
client-owned provider credentials and sandboxes remain external activation gates.
