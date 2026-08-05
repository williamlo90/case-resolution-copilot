# Governed Case Reviews

Status: Implemented in Backend Sprint B5
Date: 23 July 2026

## Purpose

A review is the human decision boundary between an AI-assisted decision brief and any future
business action. The AI may summarize a case and suggest a resolution, but it cannot reserve,
approve, reject, or execute its own proposal.

The product language stays direct:

- `Submit for review`
- `Reserve review`
- `Approve`
- `Request changes`
- `Reject`
- `Escalate`

Fingerprint, version, and authority details remain visible in the audit contract without becoming
operator-facing jargon.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/cases/{case_id}/proposals/{proposal_version}/reviews` | Submit the current proposal snapshot |
| `GET` | `/api/reviews` | Read the tenant-scoped review queue |
| `GET` | `/api/reviews/{review_id}` | Read the complete immutable review snapshot |
| `POST` | `/api/reviews/{review_id}/reserve` | Hold one review for one authorized reviewer |
| `POST` | `/api/reviews/{review_id}/decisions` | Record one final human decision |

Submission requires `case:manage` and `review:read`. Queue/detail reads require `review:read`.
Reservation requires `review:reserve`; decisions require `review:decide`. The authenticated actor
owns tenant scope and authority. Client-provided role headers do not grant either.

## Immutable Snapshot

Submission binds one complete authorization record:

- post-submission case version;
- exact proposal root and immutable proposal version;
- proposal, business-context, evidence, and risk fingerprints;
- risk-rule version;
- approval-rule ID, version, explanation, and required role;
- submitting actor and time;
- policy state, uncertainty, and financial impact;
- whether the snapshot may ever authorize B6 execution.

An approval is only execution-eligible when policy authority is relevant, the proposal is ready,
the response is not blocked, every risk is passed or explicitly requires review, and at least one
proposed action requires review.

## Human Authority

Normal customer-impacting reviews require a supervisor. An administrator is required for:

- conflicting policy authority;
- financial impact at or above the default limit configured for that currency;
- privacy or compliance risk.

The deterministic defaults cover `USD`, `EUR`, `GBP`, `SGD`, and `IDR`. A financial action in an
unconfigured currency requires an administrator rather than guessing an exchange rate. B7 settings
replace these defaults with organization-owned limits when saved. Their version is bound to the
review snapshot; changing the limits makes an open review stale without rewriting a completed
decision.

An administrator satisfies a supervisor rule. Specialists and auditors may read reviews but cannot
reserve or decide them. A submitter cannot review their own proposal.

Missing or conflicting policy may be submitted so a human can request changes, reject, or escalate.
It can never be approved.

## Reservation And Decision

Only one active reservation may exist per review. A hold lasts 30 minutes. Repeating a reservation
by the same reviewer is idempotent. A competing reviewer receives `409`.

Expiry returns the review to the queue, restores the proposal's original open state, increments the
review version, and writes a system audit event. A decision must match the active reviewer, current
review version, and exact snapshot fingerprint.

One final decision is allowed:

```text
approve | request_changes | reject | escalate
```

The decision receipt is immutable and contains actor attribution, reason, snapshot fingerprint, and
decision time. Available-decision arrays are presentation hints; the service and repository remain
authoritative.

## Freshness

A review becomes stale when:

- the case version changes;
- a newer proposal version exists;
- proposal context, evidence, risk, or rule bindings change;
- a bound policy is unpublished, not yet effective, expired, or unavailable;
- a required bound context/evidence row is unavailable;
- the record came from the legacy approval workflow.

A stale snapshot remains readable for audit but cannot be reserved or decided.

## Legacy Compatibility

`scripts/backfill_legacy_reviews.py` validates by default and writes only with `--apply`. Identity,
case, policy, and proposal backfills must run first.

The mapper preserves reservation and decision UUIDs, reviewer attribution, role, proposal version,
evidence fingerprint, reason, and timestamps. Every imported snapshot uses `APR-LEGACY`, remains
stale, and has `execution_eligible=false`. Historical approval is evidence of what happened, never
current authority.

## Deferred Evidence

Migration `20260723_0013`, deterministic tests, contract tests, Alembic head, offline PostgreSQL SQL,
and OpenAPI generation are verified. Actual migration execution, database locking, constraints, and
representative backfill remain deferred until a disposable `TEST_DATABASE_URL` is supplied.
