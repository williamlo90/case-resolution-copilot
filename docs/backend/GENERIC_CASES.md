# Generic Cases, Conversations, And Business Context

Status: Implemented in Backend Sprint B2
Date: 22 July 2026

## Boundary

B2 adds the durable generic case path without requiring a real provider or private environment
value. The authenticated actor supplies organization scope and authority. Public request data cannot
select another organization, actor, role, or owner.

The active generic tables are:

- `cases`, `case_requests`, and `case_customers`;
- `business_object_snapshots`;
- `conversation_threads` and `conversation_messages`;
- `response_drafts`.

Child records use organization-and-parent composite foreign keys. `cases.legacy_task_id` is an
internal nullable unique lineage link for the one-time compatibility backfill; it is not exposed as
authority or as a public product field.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/cases` | Tenant-scoped queue with status/category/search filters and opaque cursor pagination |
| `GET` | `/api/cases/{case_id}` | Case, request, customer, business snapshots, draft, activity, and allowed commands |
| `GET` | `/api/cases/{case_id}/conversation` | Attributable customer messages, agent messages, and internal notes |
| `POST` | `/api/cases/{case_id}/assign` | Assign the case to the authenticated active member |
| `POST` | `/api/cases/{case_id}/status` | Apply an allowlisted lifecycle transition |
| `POST` | `/api/cases/{case_id}/messages` | Append an attributable conversation message |
| `POST` | `/api/cases/{case_id}/notes` | Append an attributable internal note |
| `POST` | `/api/cases/{case_id}/draft` | Create or save a response draft |

All mutable commands use an expected version. Case and draft writes use conditional SQL updates;
stale writes return `409 version_conflict` with expected and current versions. Cursor payloads are
bound to their status, category, and query context and are rejected when reused with different
filters.

## Lifecycle

The domain transition table is the server authority:

```text
new -> investigating | information_needed
investigating -> information_needed | needs_review | waiting_customer | in_progress
information_needed -> investigating | waiting_customer
needs_review -> investigating | in_progress
waiting_customer -> investigating | information_needed
in_progress -> information_needed | needs_review | completed
completed -> no further transition
```

Available-command arrays are UI hints. They do not replace permission or transition checks.

## Honest Intelligence Boundary

B2 returns durable request, customer, source freshness, business context, conversation, draft, and
activity data. B3 adds governed policy evidence, and B4 enriches the same workspace with
source-backed facts, missing-information analysis, deterministic risk checks, immutable proposals,
uncertainty, suggested responses, and proposed actions.

Until a B4 decision brief exists, those intelligence fields remain empty or `null`. Missing, stale,
inapplicable, or conflicting authority produces an abstained, information-needed brief rather than
a fabricated recommendation. A manually saved B2 response draft remains authoritative and is never
silently overwritten by a generated suggestion.

## Credential-Free Data

`DeterministicCaseSourceSimulator` supplies billing-dispute, refund-request, and account-access
templates through one `CaseCreate` contract. After database activation, development data can be
seeded explicitly:

```powershell
python scripts/seed_identity.py
python scripts/seed_cases.py
```

Neither script runs in production. They perform no external I/O.

## Migration Boundary

Alembic creates the current case schema directly. The reconstructed runtime ships no legacy task
mapper, compatibility read route, or dual-write path. Static migration checks and tenant-scoped
unit and contract tests are part of the serial release gate. PostgreSQL migration, conflict, and
tenant-isolation execution must still be rerun through the guarded disposable-database runner for
this exact revision.
