# Frontend To Backend Handoff Contract

## Source Of Truth

Backend responses are decoded at the data boundary before reaching feature components:

- Cases: `frontend/src/domain/cases/`
- Reviews: `frontend/src/domain/reviews/`
- Actions: `frontend/src/domain/actions/`
- Policies: `frontend/src/domain/policies/`
- Quality: `frontend/src/domain/quality/`
- Administration: `frontend/src/domain/administration/`
- Notifications: `frontend/src/domain/notifications/`

Mock repositories are explicit opt-in adapters for isolated UI work. Operational routes use the API
by default and do not import fixtures.

## Transport Rules

- Backend JSON uses `snake_case`; frontend domain records use `camelCase`.
- Zod schemas validate response envelopes before mapping.
- IDs, versions, cursor values, timestamps, money, and source freshness remain explicit.
- Unknown enum values fail at the adapter instead of silently becoming UI defaults.
- Error responses use the correlated backend envelope and map to plain-language UI states.
- Protected requests use a Clerk bearer session in provider mode.
- Browser-visible role or organization values never grant backend authority.

## Queue Contract

The case queue sends search, filters, sort, page size, and an opaque cursor to the backend. The API
returns one bounded page with total, next cursor, previous cursor, offset, and limit metadata. The
frontend never fetches a fixed first 100 records and then pretends the result is complete.

## Mutation Contract

Every consequential command carries the expected version or immutable fingerprint required by the
backend. A successful HTTP response describes only the state committed by the application; it does
not imply that an external system changed unless a durable action receipt says so.

Commands include:

- case assignment, response drafts, and proposal submission;
- policy lifecycle transitions;
- review reservation and decision;
- action execution, retry eligibility, and reconciliation;
- notification read state;
- organization settings and member administration.

## Failure States

Each primary route supports loading, empty, forbidden, not found, conflict, unavailable, and retryable
failure states where relevant. Stale review or action state is presented separately from a generic
network failure because it changes what the user is allowed to do.

## Verification

- Backend and frontend case transport schemas have a shared contract check.
- Repository adapter tests cover mapping, cursor propagation, and error translation.
- Command tests verify that expected versions and fingerprints reach the backend.
- Cutover tests ensure API mode is the default and Vercel server rendering stays in the database
  region.
- TypeScript, ESLint, and serial Vitest run in the aggregate release verifier.

The contract does not prove hosted latency or external-provider behavior. Those require deployed
smoke, telemetry, and sandbox evidence.
