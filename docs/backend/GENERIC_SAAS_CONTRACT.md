# Generic SaaS Backend Contract

Status: Frozen generic contract; implemented through cutover
Date: 23 July 2026
Contract version: `2026-07-22`

## Purpose

This contract translates the completed frontend handoff into a provider-neutral backend boundary.
It replaces travel-shaped assumptions in the active application. Historical task data is reachable
only through explicit offline migration tooling.

Executable response models live in `backend/app/api/schemas`. Frontend feature components continue to
consume their existing camelCase Zod models through repository adapters; API payloads remain
snake_case.

## Fixed Decisions

1. The authenticated actor determines the organization. A request body, query, or arbitrary client
   header cannot grant tenant scope or authority.
2. Every mutable root resource carries an integer `version` starting at 1. Commands include the
   expected version and stale writes return `409`.
3. New generic persistence is additive. Existing task and travel tables are not renamed or dropped
   during the expansion phase.
4. New business writes have one owner: the generic service. Compatibility routes adapt generic data;
   they do not create a second write path.
5. PostgreSQL remains the durable source of truth. Simulators and deterministic adapters remain the
   default until private environment activation.
6. Public IDs are opaque and unique inside an organization. Internal UUIDs never cross the API.
7. Money crosses the API as an exact decimal string plus an ISO 4217 currency code. The frontend
   adapter converts it to its presentation number only after validation.
8. No response exposes secrets, chain-of-thought, raw provider payloads, or unnecessary PII.

## Tenant And Authority Boundary

The B1 auth adapter resolves an immutable request actor containing:

```text
actor_id
organization_id
actor_kind: member | service | system
role
permissions
authentication_mode: deterministic_development | provider
```

Routes pass this actor context to services. Services pass `organization_id` explicitly to
repositories. Repositories must include organization scope in every lookup and mutation. A resource
from another organization is returned as `404` to avoid confirming its existence. A visible resource
with an unauthorized command returns `403`.

Development identity headers are only accepted by the deterministic development adapter. They are
disabled when a production auth adapter is selected and are never described as production login.

## Resource Contract

| Resource | Public prefix | Mutable version | Tenant scope | Primary purpose |
| --- | --- | --- | --- | --- |
| Organization | `ORG-` | Yes | Root | SaaS account and governance owner |
| Member | `USR-` | Yes | Direct | Role, status, and explicit authority |
| Invitation | `INV-` | Yes | Direct | Attributable membership onboarding |
| Case | `CS-` | Yes | Direct | Complex customer-case decision lifecycle |
| Conversation | `CV-` | Yes | Direct | Customer messages, replies, and internal notes |
| Business snapshot | `CTX-` | Yes | Direct | Immutable typed context captured from a source |
| Policy | `POL-` | Yes | Direct | Lifecycle and applicability root |
| Policy version | `POLV-` | Version identity | Direct | Immutable published evidence source |
| Evidence | `EVD-` | Immutable | Direct | Exact policy-version citation and fingerprint |
| Proposal | `PRP-` | Yes | Direct | Structured evidence-bound resolution |
| Review | `RV-` | Yes | Direct | Immutable authorization snapshot |
| Action | `AC-` | Yes | Direct | Controlled provider-neutral side effect |
| Connection | `CON-` | Yes | Direct | Capability and health metadata without secrets |
| Audit event | `AUD-` | Immutable | Direct | Attributable business and governance history |

Public prefixes aid operators but are not authorization evidence. Database relationships use UUIDs
and organization-scoped foreign keys.

## Generic Case Contract

A case never requires booking, passenger, itinerary, or airline fields. All case categories use the
same lifecycle:

```text
new -> investigating -> information_needed | needs_review | waiting_customer
    -> in_progress -> completed
```

The workspace contains:

- request and customer context;
- one or more typed business-object snapshots;
- verified facts and missing information;
- applicable version-bound policy evidence;
- deterministic risk checks;
- a structured proposal, response draft, and proposed actions;
- business-readable activity and server-derived available commands.

B2 persists and returns the source-backed portions of this workspace. B3 adds immutable governed
policy evidence. B4 adds source-backed facts, explicit information gaps, deterministic risk checks,
immutable proposal versions, suggested responses, proposed actions, and safe analysis checkpoints.
The generated brief abstains instead of authorizing a consequential action when evidence or required
context is missing, stale, inapplicable, or conflicting.

Initial business snapshot types are `invoice`, `payment`, `subscription`, `account`, `order`,
`delivery`, and `other`. Their bounded `fields` map carries display context only. Authorization,
money, lifecycle state, idempotency, and evidence bindings remain typed columns or typed resources.

## API Surface By Delivery Sprint

| Sprint | Generic API surface |
| --- | --- |
| B1 | `/api/session`, `/api/organizations/current`, `/api/members`, `/api/invitations` |
| B2 | `/api/cases`, `/api/cases/{case_id}`, assignment, messages, notes, and draft commands |
| B3 | `/api/policies`, policy versions, lifecycle commands, and evidence retrieval |
| B4 | case proposal start/read commands and deterministic evaluation results |
| B5 | `/api/reviews`, reservation, decision, and immutable snapshot reads |
| B6 | `/api/actions`, execution, safe retry, reconciliation, and `/api/connections` |
| B7 | `/api/quality`, case audit export, notifications, members, and settings |
| B8 | compatibility cutover, operational health, and frontend repository integration |

Legacy task, agent-run, and travel-shaped approval routes are not mounted. No feature may depend on
their model, generic writes never dual-write to their tables, and migration access is restricted to
explicit backfill commands.

## Response And Command Envelopes

Single-resource reads return:

```json
{
  "data": {},
  "meta": {
    "data_mode": "demo",
    "contract_version": "2026-07-22"
  }
}
```

Lists return `items`, `next_cursor`, `total`, and the same `meta`. Cursors are opaque and tied to an
allowlisted filter/sort set. Commands return the authoritative resource plus a durable receipt when
the command is consequential. A success message by itself is not evidence of a state change.

Actor, organization, role, approval, and idempotency values that grant authority are always derived
or verified server-side. Available-command arrays are presentation hints, never authorization.

## Compatibility Mapping

| Legacy concept | Generic destination | Rule |
| --- | --- | --- |
| `tasks` / `RF-*` | `cases` / `CS-*` | Preserve legacy ID as `source_id`; mint stable case ID |
| `requests` | case request and conversation | Preserve received time, channel, and original text |
| `customer_snapshots` | customer context | Copy only required support fields |
| `booking_snapshots` | business-object snapshot | Convert known values; never require travel fields |
| `proposal_versions` | proposals | Preserve immutable version and lineage; bind generic evidence only when exact equivalence is provable |
| approval reservations/decisions | reviews | Bind to one complete snapshot fingerprint |
| tool attempts/receipts | actions/attempts/receipts | Preserve side-effect knowledge and idempotency |
| audit events | organization-scoped audit | Preserve correlation and attribution |

Legacy aliases have removal criteria in the migration strategy. They are not public product models.

## B0 Acceptance Record

- Executable Pydantic schemas cover every resource named in this contract.
- Contract tests reject required travel fields and unknown payload fields.
- UTC timestamps, exact money serialization, optimistic versions, and response metadata are tested.
- Tenant and repository boundaries are explicit before schema migration begins.
- No database, credential, provider, or active endpoint was changed in B0.

## B2 Implementation Record

- Generic case, conversation, business snapshot, and draft persistence is additive and
  tenant-scoped.
- Case queue/detail and explicit assignment, status, message, note, and draft commands are active.
- Mutable writes use optimistic versions and stable conflict responses.
- Three deterministic case templates share the same lifecycle and source adapter contract.
- A dry-run-first legacy mapper preserves lineage without making legacy tables a second write owner.
- PostgreSQL execution remains a Plan C evidence item; deterministic/static success is not presented
  as a live migration result.

## B3 Implementation Record

- Policy roots and versions are tenant-scoped, owner-attributed, effective-dated, and optimistic.
- Published and scheduled versions are immutable; evidence records bind exact version, clause,
  hashes, applicability, and retrieval provenance.
- Publication conflicts are evaluated per decision scope and overlapping applicability rather than
  treating every applicable policy as mutually exclusive.
- Missing, stale, inapplicable, or conflicting authority abstains without recording evidence.
- The legacy policy corpus is an explicitly linked compatibility input with no dual-write path.
- PostgreSQL execution remains deferred; the integration test is prepared but skips without a
  disposable `TEST_DATABASE_URL`.

## B4 Implementation Record

- Decision generation reads the current tenant-scoped case and refreshes governed policy evidence
  server-side before computing an input fingerprint.
- Proposal roots use optimistic versions; proposal versions, facts, gaps, risks, evidence/context
  bindings, actions, response drafts, and checkpoints are immutable snapshots.
- Repeating the same case/evidence/context input returns the same analysis and proposal version.
  Changing the case version produces a new immutable proposal version.
- The deterministic engine does not infer duplicate settlement from an attempt count and abstains
  for missing, stale, inapplicable, or conflicting authority.
- Checkpoints store business-safe summaries and fingerprints, never chain-of-thought, prompts, or raw
  provider payloads.
- The legacy proposal backfill is dry-run-first and imports historical records as low-confidence,
  blocked, information-needed history. It preserves lineage and source version without fabricating
  generic evidence or context bindings.
- PostgreSQL execution remains deferred; the decision API, backfill, and migration integration tests
  are prepared but skip without a disposable `TEST_DATABASE_URL`.

## B5 Implementation Record

- Review submission binds the post-command case version and exact proposal, context, evidence, risk,
  risk-rule, and approval-rule fingerprints.
- The review queue, detail, reservation, and decision APIs are tenant-scoped and authorize before
  database access.
- Supervisor and administrator authority is server-derived. The submitter cannot reserve their own
  review, and only one active reservation may exist.
- Missing/conflicting policy and unsafe risk/response states may be changed, rejected, or escalated
  but never approved.
- Decisions are immutable receipts; stale snapshots remain readable but cannot be reserved or
  decided.
- The legacy review backfill preserves attribution and lineage while forcing every imported
  approval to remain stale and non-executable.
- PostgreSQL execution remains deferred; review API, migration, and backfill integration tests are
  prepared but skip without a disposable `TEST_DATABASE_URL`.

## B6 Implementation Record

- An approved review materializes a separate tenant-scoped action in the same transaction; approval
  never calls a target.
- Execution revalidates exact review/proposal/case authority, approval expiry, permission,
  connection health, idempotency, and duplicate receipt state before creating an attempt.
- Provider calls occur outside database locks. Safe failure, confirmed completion, and outcome
  unknown remain distinct durable states.
- Unknown outcomes cannot be retried blindly. Read-only reconciliation must confirm completion or
  provide explicit terminal absence evidence before the action can complete or become safely
  retryable. A transient lookup miss or manual note is not enough.
- Connection APIs expose capability, environment, health, and credential status without storing or
  returning secret values.
- Deterministic demo connections and the action gateway require no credentials. Real adapters and
  `.env` activation remain deferred.
- The dry-run-first legacy action backfill preserves attempt/receipt lineage and side-effect
  knowledge, redacts payloads, never replays a target write, and keeps imported actions
  non-executable.
- PostgreSQL execution remains deferred; action, migration, and legacy backfill integration tests
  are prepared but skip without a disposable `TEST_DATABASE_URL`.

## B7 Implementation Record

- Quality evidence, case audit export, notifications/outbox, member administration, typed settings,
  approval-rule versioning, and non-destructive governance state are tenant-scoped.
- Projectors are explicit one-shot commands; no scheduler, provider dispatcher, or background worker
  starts with the application.
- PostgreSQL execution remains deferred; B7 integration tests skip without a disposable
  `TEST_DATABASE_URL`.

## B8 Implementation Record

- Primary frontend reads use generic API repositories by default; mock repositories require explicit
  opt-in.
- Case draft/review, review reservation/decision, action recovery, connection test, invitation,
  member, and settings commands wait for backend responses and preserve structured failures.
- Legacy writes are retired by default while authenticated compatibility reads remain available.
- Readiness stays honest: liveness is process-only and readiness requires the configured database.
- Authentication, provider, migration, backup/restore, incident, and post-ENV runbooks are prepared.
- Policy authoring remains read-only in the active UI because the detail response does not expose the
  exact applicability needed for a safe draft copy; backend lifecycle APIs remain governed.
- External database, identity, provider, backup, browser, and manual acceptance evidence remains
  Plan C work.
