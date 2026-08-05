# API Conventions

Status: Revised and implemented through generic SaaS Backend Sprint B7.

## Boundary

- Base path: `/api`.
- JSON property names: `snake_case`.
- Resource paths: plural nouns.
- Public identifiers are opaque strings, unique within an organization, and never database sequence
  IDs.
- All timestamps use RFC 3339/ISO 8601 UTC with a `Z` suffix.
- Money is `{ "amount": "125.00", "currency": "USD" }`; amounts are exact decimal strings. Frontend
  adapters may convert validated values for presentation, but financial persistence never uses binary
  floating point.
- Mutable resources expose an integer `version`.
- Clients send expected versions through the request body for domain commands.

Generic endpoint families are delivered incrementally through B1-B7:

```text
GET /api/health/live
GET /api/health/ready
GET /api/session
GET /api/cases
GET /api/cases/{case_id}
GET /api/reviews
GET /api/reviews/{review_id}
GET /api/actions
GET /api/actions/{action_id}
GET /api/policies
GET /api/policies/{policy_id}
GET /api/connections
GET /api/members
GET /api/quality
GET /api/notifications
GET /api/settings/{section}
```

Implemented B3 policy commands use explicit version subresources for draft creation, review,
publication, scheduling, retirement, and source recovery. Case evidence is read or refreshed through
`/api/cases/{case_id}/policy-evidence`. Retrieval status is explicit: `relevant`, `missing`,
`inapplicable`, `stale`, or `conflicting`; only `relevant` results may create immutable citations.

Implemented B4 decision commands are:

```text
POST /api/cases/{case_id}/proposals
GET /api/cases/{case_id}/proposals/current
GET /api/cases/{case_id}/proposals/{version}
```

Generation accepts only `expected_case_version`. Actor, tenant, current context, governed evidence,
fingerprints, rule versions, and proposal version are server-owned. Repeating identical durable input
is idempotent. A changed case version returns `409`; historical proposal versions remain immutable.
An analysis may be `completed` while still requiring information, but any missing, stale,
inapplicable, or conflicting policy authority makes the analysis `abstained` and blocks consequential
actions.

Implemented B5 review commands are:

```text
POST /api/cases/{case_id}/proposals/{proposal_version}/reviews
GET /api/reviews
GET /api/reviews/{review_id}
POST /api/reviews/{review_id}/reserve
POST /api/reviews/{review_id}/decisions
```

Submission accepts only `expected_case_version`. Reservation accepts only `expected_version`.
Decision accepts the expected review version, exact server-issued snapshot fingerprint, one
allowlisted decision, and a human reason. Tenant, actor, role, approval rule, policy state, and
execution eligibility are never client-authoritative. A stale review returns `409` and remains
readable for audit.

Implemented B6 action and connection commands are:

```text
GET /api/actions
GET /api/actions/{action_id}
POST /api/actions/{action_id}/execute
POST /api/actions/{action_id}/retry
POST /api/actions/{action_id}/reconcile
POST /api/actions/{action_id}/manual-outcome
POST /api/actions/{action_id}/escalate
GET /api/connections
GET /api/connections/{connection_id}
POST /api/connections/{connection_id}/test
```

Execute and retry accept only `expected_version`. Reconciliation checks the target without another
write. Manual outcome and escalation also require a plain-language reason. Approval lineage,
idempotency, target selection, actor authority, side-effect state, and available commands are
server-owned. Unknown target outcomes return durable recovery state and never expose blind retry.

Implemented B7 operational endpoints are:

```text
GET /api/quality
GET /api/quality/cases/{case_id}
POST /api/cases/{case_id}/audit-export
GET /api/notifications
POST /api/notifications/{notification_id}/read
POST /api/notifications/read-all
PATCH /api/members/{member_id}
POST /api/invitations/{invitation_id}/revoke
GET /api/settings/{section}
PUT /api/settings/{section}
```

Quality evidence is attributable and case-linked. Settings and member mutations require an expected
version. Approval-setting versions are server-bound to review snapshots. Notification reads are
recipient-scoped. Audit export appends its own audit event and returns redacted details. Retention
state is non-destructive; no API command purges customer data.

An endpoint listed here is a naming contract, not an implementation claim. OpenAPI records the
implemented subset. Legacy task, agent-run, and travel-shaped approval routes are not mounted.

## Organization And Actor Context

- Authentication resolves the actor and organization before product route handling.
- Client-provided tenant IDs, roles, permissions, and available-command flags never grant authority.
- Routes pass immutable actor context to services; services pass organization scope to repositories.
- Cross-organization resource reads return `404`. Unauthorized commands on visible resources return
  `403`.
- Deterministic development identity is explicitly labelled and disabled by production auth mode.
- `X-Actor-ID` is accepted only by the deterministic development adapter and must match its actor
  registry. `X-Actor-Role` is ignored and retained only for temporary CORS compatibility.
- Provider mode never falls back to deterministic identity; an unavailable provider fails closed.

## Correlation

- Clients may send `X-Correlation-ID`.
- The API validates or generates it and returns `X-Correlation-ID` on every response.
- The same ID is propagated into logs, audit events, runs, tool attempts, and provider-simulator calls.
- Correlation IDs aid investigation; they are not idempotency keys.

## Errors

Every non-2xx product error uses:

```json
{
  "error": {
    "code": "proposal_version_conflict",
    "message": "The proposal changed and must be reviewed again.",
    "correlation_id": "corr_01J...",
    "details": {
      "expected_version": 1,
      "current_version": 2
    }
  }
}
```

Rules:

- `code` is stable and machine-readable.
- `message` is safe for operator display.
- `details` contains no secrets, chain-of-thought, raw provider payload, or unnecessary PII.
- Validation errors follow the same envelope.
- Stack traces never cross the API boundary.

Baseline status usage:

| Status | Meaning |
|---:|---|
| `400` | Semantically invalid request not covered by field validation |
| `401` | Authentication required |
| `403` | Actor lacks authority |
| `404` | Resource does not exist or is not visible |
| `409` | Version, state, reservation, or idempotency conflict |
| `422` | Pydantic field validation failed |
| `424` | A required downstream capability is unavailable for this command |
| `429` | Rate limit exceeded |
| `500` | Unexpected internal failure |
| `503` | Required dependency is not ready |

Provider failure is normally persisted as workflow state and returned through the relevant resource;
it is not automatically translated into an HTTP `500`.

## Response Envelopes

Single-resource responses use `data` and `meta`. List responses use `items`, `next_cursor`, `total`,
and `meta`. Metadata currently contains:

```json
{
  "data_mode": "demo",
  "contract_version": "2026-07-22"
}
```

`data_mode` describes the actual adapter mode and is never inferred by the frontend.

## Lists

Resource lists use cursor pagination:

```json
{
  "items": [],
  "next_cursor": null
}
```

Filters and sort fields are allowlisted per resource. Common parameters are `query`, `sort`, `cursor`,
and `limit`; resource-specific filters are documented in OpenAPI. A cursor is opaque and valid only
for the filter and sort context that produced it. The default and maximum limits are fixed by
implementation.

## Commands and concurrency

- Consequential commands are explicit subresources, not generic `PATCH` operations.
- The authenticated actor supplies attribution; command bodies never accept authoritative actor,
  organization, role, or permission values.
- Approval commands include `expected_proposal_version` and `expected_evidence_version`.
- Execution commands require a persisted valid approval; frontend flags are never authority.
- External writes use a server-generated, persisted idempotency key.
- A stale version returns `409`; the server never silently applies a command to newer data.

## Compatibility

- OpenAPI is the backend contract source once FastAPI exists.
- Frontend Zod schemas validate responses at the adapter boundary.
- Additive fields are permitted; removal or semantic changes require compatibility review.
- No `/v1` prefix is introduced until a real breaking-version requirement exists.
- Generic schema contract `2026-07-22` is exposed through response metadata.
- `RF-*` identifiers are accepted only by explicit migration tooling. Product routes and new
  records use cases and `CS-*` identifiers.
- Historical compatibility tables are isolated behind offline backfill tooling. Generic writes
  never dual-write to legacy task tables.
