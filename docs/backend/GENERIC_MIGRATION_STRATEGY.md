# Generic SaaS Migration Strategy

Status: Implemented through Backend Sprint B8; database execution and legacy table removal deferred
Date: 23 July 2026

## Current Constraint

The generic backend is active, but the repository still contains older task, booking, proposal,
approval, tool, and audit records needed for migration lineage. Removing them before activated
database evidence would mix semantic cutover with destructive foreign-key changes and make rollback
unsafe.

## Decision

Use an expand, migrate, cut over, and contract sequence. B0 creates no migration. B1 and later sprints
add schema in small reviewed revisions. No automated downgrade may drop populated generic tables.

## Invariants

1. One organization owns every business row.
2. Tenant roots use internal UUIDs and an organization-scoped public ID uniqueness constraint.
3. High-risk child tables carry `organization_id` and use composite tenant-parent foreign keys where
   practical, preventing a child from referencing another tenant's parent.
4. Compatibility reads may adapt data. Compatibility dual-writes are prohibited.
5. Backfills are restartable and record counts before cutover.
6. Existing source IDs, timestamps, versions, fingerprints, receipts, and correlation IDs are
   preserved.
7. Unknown external outcomes remain unknown throughout migration.

## Delivery Sequence

| Sprint | Additive database work | Cutover rule |
| --- | --- | --- |
| B1 | Organizations, memberships, invitations, role grants; organization scope for audit | Seed one labelled demo organization; auth context owns tenant selection |
| B2 | Cases, case requests, conversations, messages, drafts, business snapshots, source snapshots | Backfill legacy tasks once; new writes use case service only |
| B3 | Policy roots, lifecycle metadata, applicability, immutable version bindings | Existing neutral policy versions may be linked, never rewritten |
| B4 | Generic proposal/context/risk bindings and orchestration checkpoints | Legacy refund graph becomes compatibility-only |
| B5 | Review roots, immutable snapshot fingerprints, reservations, decisions | Existing approvals are copied with attribution and exact proposal version |
| B6 | Actions, connections, attempts, receipts, reconciliation state | Existing tool records remain evidence; no action is replayed during migration |
| B7 | Settings, outbox, retention/redaction state, quality projections | Metrics switch only after record-count and tenant-scope checks pass |
| B8 | Compatibility views/adapters and final read cutover | Legacy tables become read-only; removal remains deferred |

B2 implementation note: revision `20260722_0010` is the single Alembic head. It adds generic case,
request, customer, business snapshot, conversation, message, and draft tables with tenant composite
foreign keys and a populated-data downgrade guard. The dry-run-first backfill preserves
`legacy_task_id`, source ID, timestamps, money, and correlation. Executing B1-B2 against PostgreSQL
remains deferred until a disposable test URL is supplied; static head and offline SQL evidence are
not database migration claims.

B3 implementation note: revision `20260722_0011` is the single Alembic head. It adds policy roots,
governed versions, parsed clauses, and exact case evidence with tenant composite foreign keys. The
legacy policy backfill preserves version lineage, hashes, embeddings, and effective windows without
rewriting the old corpus. Executing B1-B3 against PostgreSQL remains deferred; offline SQL generation
does not prove database behavior.

B4 implementation note: revision `20260722_0012` is the single Alembic head. It adds analysis runs,
safe checkpoints, proposal roots and immutable versions, exact governed evidence/context bindings,
proposed actions, and suggested response snapshots. The dry-run-first legacy proposal backfill
preserves source proposal versions and UUID lineage but marks them information-needed because the
old workflow did not prove equivalent generic context and policy bindings. Executing B1-B4 against
PostgreSQL remains deferred; offline SQL generation does not prove database behavior.

B5 implementation note: revision `20260723_0013` is the single Alembic head. It adds review roots,
complete immutable authorization snapshots, exclusive reservations, and immutable decision
receipts. The dry-run-first legacy review backfill preserves reservation/decision lineage and
reviewer attribution, but all imported approvals are stale and non-executable. Executing B1-B5
against PostgreSQL remains deferred; offline SQL generation does not prove database behavior.

B6 implementation note: revision `20260723_0014` is the single Alembic head. It adds secret-free
connection metadata and health receipts plus controlled actions, attempts, target receipts, and
reconciliation records. Approval-to-action creation is additive and does not execute a provider.
The dry-run-first legacy action backfill preserves side-effect and receipt lineage without replaying
the source action. Executing B1-B6 against PostgreSQL remains deferred; offline SQL generation does
not prove locking, constraints, or provider behavior.

B7 implementation note: revision `20260723_0015` is the single Alembic head. It adds typed
organization settings, recipient-scoped notifications, a destination-redacted outbox,
non-destructive case governance state, and attributable quality projections. Open reviews bind the
current approval-settings version and fail closed when it changes. Quality, notification, and
governance projectors are explicit deterministic commands; no worker or external delivery provider
is started. Executing B1-B7 against PostgreSQL remains deferred; offline SQL generation does not
prove row locks, constraints, tenant isolation, or retention behavior.

B8 implementation note: every primary frontend repository now reads the generic case, review,
action, policy, quality, connection, member, organization, session, and settings APIs. Operational
commands use generic endpoints and only report success after an API response. Legacy task writes
return `410 Gone` by default; the opt-in flag exists only for bounded compatibility integration
tests. Legacy reads and tables remain available for lineage and migration verification. No new
schema revision was required. External PostgreSQL execution and compatibility table removal remain
deferred to Plan C.

## Case Backfill

Each legacy task receives one generic case with:

- a new `CS-*` public ID;
- the legacy `RF-*` value stored as `source_id`;
- a nullable unique `legacy_task_id` used only for compatibility lookup and idempotent backfill;
- category mapped through an explicit allowlist;
- request, customer, and known context copied without inventing missing data;
- original timestamps, correlation IDs, exposure, and source references preserved.

Legacy booking context is translated into the closest generic business snapshot only when its source
meaning is known. Unmapped values are retained in migration evidence, not silently copied into an
untyped production payload.

## Proposal Backfill

Run identity, case, and governed-policy backfills before the proposal backfill. Each imported legacy
proposal:

- retains its immutable source version and `legacy_proposal_version_id`;
- creates a stable generic proposal and analysis lineage without dual-writing legacy tables;
- remains `information_needed`, low confidence, and blocked from execution;
- records the historical outcome, impact, rationale, risk labels, response draft, and a redacted
  action snapshot;
- does not create generic evidence or context bindings unless a future reviewed migration can prove
  exact equivalence;
- is idempotent and refuses a source-version collision with an already generated generic proposal.

Validation is the default. `--apply` is explicit, and the proposal backfill must run before new B4
proposal generation if source version numbers are to remain unchanged.

## Review Backfill

Run the proposal backfill before the review backfill. Each imported legacy review:

- retains source reservation and decision UUID lineage;
- retains reviewer attribution, role, proposal version, evidence fingerprint, reason, and time;
- maps old outcomes through an explicit allowlist;
- records the old decision as immutable history;
- uses `APR-LEGACY`, remains stale, and has `execution_eligible=false`;
- never reserves a current review and never queues or replays an action.

`scripts/backfill_legacy_reviews.py` validates by default. `--apply` is explicit and requires an
active importer membership for attribution.

## Action Backfill

Run proposal and review backfills before action backfill. Each imported legacy action:

- retains source attempt and optional external receipt UUID lineage;
- preserves recorded side-effect state, error code, timestamps, external reference, and
  deterministic idempotency identity;
- stores request/response fingerprints and redacted parameters rather than raw provider payloads;
- remains `execution_eligible=false`, even when historical evidence proves completion;
- records an unavailable legacy actor honestly instead of assigning a fabricated role;
- never calls an adapter or replays a target write.

`scripts/backfill_legacy_actions.py` validates by default. `--apply` is explicit.

## Tenant Backfill

Before B1 activation, existing rows belong to one labelled demo organization. The backfill must:

1. create the organization and deterministic development members;
2. add nullable organization columns;
3. populate child rows from their durable root;
4. verify zero null tenant roots and zero cross-tenant relationships;
5. add non-null and composite constraints only after verification.

PostgreSQL row-level security may be added as defense in depth after real-database tests. It will not
replace route, service, repository, and foreign-key tenant enforcement.

## Rollback

- Expansion migrations roll back application code first and leave additive tables intact.
- Before generic writes are enabled, rollback can return reads to the legacy service.
- After generic writes begin, rollback requires write suspension and reconciliation; old code cannot
  safely own records it cannot represent.
- A migration downgrade must refuse to drop populated generic tables unless a reviewed export and
  restore path exists.
- Provider execution is never replayed as part of schema recovery.

## Compatibility Removal Criteria

Legacy task routes and tables remain until all conditions hold:

- every primary frontend repository reads generic endpoints (met in B8);
- record counts and sampled fingerprints match migration evidence;
- no active run, review, action, or uncertain outcome references only a task row;
- tenant isolation and rollback are verified against the activated PostgreSQL environment;
- audit export resolves both old and new identifiers;
- one release has completed without compatibility-route consumers.

Removal is a separate approved migration after environment activation, not part of B8 by default.

## Evidence Required Per Migration

- generated SQL review and Alembic head check;
- empty-database upgrade;
- representative legacy-data upgrade;
- row counts and null/cross-tenant checks;
- application contract tests in compatibility and generic modes;
- downgrade refusal or reviewed safe downgrade behavior;
- no credentials or production data in captured evidence.
