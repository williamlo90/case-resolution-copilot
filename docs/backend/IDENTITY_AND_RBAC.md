# Identity And RBAC Foundation

Status: Implemented for Backend Sprint B1
Date: 22 July 2026

## Security Boundary

The server resolves one immutable actor context before product route handling:

```text
actor_id
organization_id
name
kind
role
permissions
authentication_mode
```

Client-provided organization IDs, roles, permissions, and available-command values never grant
authority. During deterministic development, `X-Actor-ID` selects only a known fixture identity.
`X-Actor-Role` remains accepted by CORS for legacy clients but is ignored by authentication and will
be removed with compatibility routes.

Production configuration rejects deterministic development authentication. Provider mode currently
uses a fail-closed adapter and returns `503 authentication_unavailable` until a real provider is
selected during Plan C.

## Deterministic Actors

| Actor | Role | Intended verification use |
| --- | --- | --- |
| `USR-0001` | Specialist | Case work without review or administration authority |
| `USR-0002` | Supervisor | Review reservation/decision and controlled action authority |
| `USR-0003` | Administrator | Organization, membership, policy, connection, and settings authority |
| `USR-0004` | Auditor | Read-only operational and audit evidence |
| `SVC-0001` | Service actor | Narrow workflow and action execution boundary |

Compatibility IDs `operator-1`, `reviewer-1`, and `reviewer-2` map to fixed server-owned roles so old
approval tests and records remain readable. A supplied role header cannot change those roles.

## Role Matrix

| Capability | Specialist | Supervisor | Administrator | Auditor |
| --- | :---: | :---: | :---: | :---: |
| Read and manage cases | Yes | Yes | Yes | Read only |
| Read reviews | Yes | Yes | Yes | Yes |
| Reserve and decide reviews | No | Yes | Yes | No |
| Execute and reconcile actions | No | Yes | Yes | No |
| Read policies and connections | Yes | Yes | Yes | Yes |
| Manage members, policies, connections, settings | No | No | Yes | No |
| Read quality evidence | No | Yes | Yes | Yes |
| Read restricted audit evidence | No | No | Yes | Yes |

The permission enum and role matrix live in `backend/app/domain/identity.py`. Routes enforce
permission before dependency readiness where practical, services enforce it again, and repositories
receive only the organization resolved from the actor.

## Persistence

Alembic revision `20260722_0009` adds:

- `organizations`;
- tenant-scoped `memberships`;
- tenant-scoped `invitations`;
- nullable organization and generic-subject fields on the existing audit table;
- generic audit events that do not require a legacy task.

The downgrade refuses to drop populated B1 identity or generic audit data. The migration does not
insert fixtures automatically. `scripts/seed_identity.py` creates the labelled development
organization and four member identities only when explicitly run outside production.

## Active API

- `GET /api/session`
- `GET /api/organizations/current`
- `GET /api/members`
- `GET /api/invitations`
- `POST /api/invitations`

Generic case rows are organization-scoped. Legacy task, orchestration, and travel-shaped approval
routes are not mounted; inherited rows are reachable only by explicit migration tooling.

## Failure Semantics

- Missing or unknown identity: `401 authentication_required`.
- Known actor without permission: `403` with a stable domain code.
- Resource from another organization: `404` after tenant-scoped lookup.
- Provider mode without configured adapter: `503 authentication_unavailable`.
- Organization storage not configured: `503 database_not_configured` after authentication and
  authorization.
- Duplicate pending invitation: `409 invitation_conflict`.

## Evidence Boundary

Verified without external configuration:

- role spoofing is ignored;
- permission matrices and service-actor limits;
- tenant scope cannot be supplied to organization services by the client;
- unauthorized routes fail before database readiness is disclosed;
- migration chain has one head;
- ORM tenant constraints and generic audit nullability.

Deferred until a disposable PostgreSQL URL is supplied:

- executing upgrade/downgrade revision `0009`;
- database-enforced uniqueness and foreign-key checks;
- organization route integration and cross-tenant query evidence;
- seeded identity persistence across process restart.
