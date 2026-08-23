# Governed Policy Lifecycle

Status: Implemented in Backend Sprint B3; PostgreSQL execution deferred
Date: 22 July 2026

RAG V2 design: `docs/backend/GOVERNED_RAG_V2.md`

## Purpose

The governed policy service gives each organization an attributable policy root, reviewable draft
versions, immutable published versions, explicit applicability, and exact case evidence. It is the
authority boundary for B4 decision briefs; the legacy policy corpus remains an isolated
compatibility input.

## Lifecycle

```text
draft -> in_review -> published
                   -> scheduled -> published by effective-time selection
published | scheduled -> retired
source failure -> parsing_failed -> recovered draft
overlapping authority -> conflicting -> replacement draft
```

Only an administrator can create or manage a policy. Specialists and auditors can read policies;
case evidence refresh additionally requires case-management authority. The authenticated actor owns
tenant selection and attribution. Body fields and identity headers cannot change organization or
role.

Published and scheduled versions are immutable. A scheduled replacement does not retire the active
version early. Cancelling it restores the prior active version, and the next draft receives a new
monotonic version number. Immediate publication retires superseded versions at the new effective
boundary.

## Applicability And Conflicts

Every version declares:

- a bounded decision scope;
- case categories;
- products and regions;
- request channels;
- customer tiers;
- an optional effective window.

`all` is explicit; an absent dimension is never treated as a wildcard. Publication is blocked when
another tenant-visible version overlaps the same decision scope, applicability, and effective
window. Policies from different decision scopes can apply to the same case without creating a false
conflict.

## Evidence Contract

Evidence retrieval derives category, product, region, channel, and customer tier from the persisted
case workspace. The client cannot submit retrieval authority or applicability. Retrieval returns one
of:

```text
relevant | missing | inapplicable | stale | conflicting
```

Only `relevant` results are recorded. Each `EVD-*` row binds the case to one policy UUID, immutable
policy-version UUID, clause UUID, content hashes, applicability label, effective window, retrieval
versions, score, and fingerprint. Repeating the same retrieval is idempotent by
organization/case/fingerprint. Missing, stale, inapplicable, and conflicting results abstain and
write no citation.

The deterministic embedding and Markdown parser are local demo adapters. They provide reproducible
development behavior, not a claim of production semantic-search quality.

## API Surface

- `GET /api/policies`
- `POST /api/policies`
- `GET /api/policies/{policy_id}`
- `POST /api/policies/{policy_id}/versions`
- `POST /api/policies/{policy_id}/versions/{version}/submit-review`
- `POST /api/policies/{policy_id}/versions/{version}/publish`
- `POST /api/policies/{policy_id}/versions/{version}/schedule`
- `POST /api/policies/{policy_id}/versions/{version}/retire`
- `POST /api/policies/{policy_id}/retry-source`
- `GET /api/cases/{case_id}/policy-evidence`
- `POST /api/cases/{case_id}/policy-evidence/refresh`

Mutable commands require both the expected policy root version and expected policy-version record
version. Stale writes return `409 version_conflict`. Cross-tenant reads return `404`.

## Migration And Activation

Alembic creates policy roots, governed versions, parsed clauses, and case evidence directly. The
reconstructed runtime has no legacy policy mapper or dual-write path. `scripts/seed_policies.py` is
disabled in production and requires a configured database. PostgreSQL upgrade, locking, constraints,
and query plans must be rerun through the guarded disposable-database runner for this exact revision;
static checks alone are not database evidence.
