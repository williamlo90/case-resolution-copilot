# Full-Stack Performance Boundaries

## Purpose

This milestone treats performance as bounded work rather than a single speed score. The application
must keep database sessions short, make large queues reachable without loading every row, limit the
amount of related case data returned at once, and avoid shipping secondary workspace panels before
the user opens them.

The checks in this milestone are regression evidence. They are not production load-test results and
do not establish a throughput or latency service-level objective.

## Implemented Boundaries

### Database and model calls

- Decision-brief generation reads the required snapshot in one database transaction.
- The database transaction closes before the external model call begins.
- A second short transaction persists the result after validating the generation lease.
- Case workspace collections have explicit limits instead of unbounded relationship loading.
- Actor resolution joins membership and organization data in one query.

### Queue and API transport

- The case queue uses opaque keyset cursors rather than database offsets for traversal.
- The API enforces a maximum page size of 100 records.
- The frontend requests one server page at a time and preserves next and previous cursors.
- Contract tests keep backend and frontend pagination envelopes aligned.
- Cases beyond the first 100 remain reachable through server-provided cursors.

### Frontend delivery

- Decision Brief is the initial workspace view.
- Conversation, Evidence, and Activity panels are loaded as separate chunks when selected.
- Loading states have stable dimensions so deferred content does not shift the workspace layout.
- TypeScript, ESLint, and serial Vitest checks remain the default lightweight verification path.

## Verification

The milestone verification suite covers:

- database-session lifetime around model inference;
- root-query reuse and bounded workspace collections;
- keyset query construction;
- identity lookup query count;
- backend transport-schema stability;
- database index plans when `TEST_DATABASE_URL` is available;
- frontend cursor navigation and deferred workspace panels.

The scale-plan test skips when an isolated PostgreSQL test database is not configured. A skip is not
evidence that the production database has the expected indexes; migration and query-plan validation
must be repeated against a disposable database before release.

## Cost Model

The primary cost controls are architectural:

1. Retrieve only the policy and case context needed for the current decision.
2. Bound every collection and page at the API boundary.
3. Keep database connections free while waiting on external AI providers.
4. Avoid duplicate model calls through generation leases and single-flight controls.
5. Defer non-default frontend panels until the user asks for them.

These controls reduce avoidable database, network, model, and browser work. They do not replace
observability. Hosted latency, model-token usage, query duration, and failure rates still need to be
measured under representative pilot traffic.

## Resource-Conscious Local Workflow

- Run backend and frontend checks sequentially.
- Keep Vitest at one worker.
- Do not leave development servers or watch processes running after verification.
- Use browser automation only for a bounded acceptance journey when static and component checks are
  insufficient.
- Do not infer production performance from Next.js development compilation time.

## Residual Risks

- Query plans depend on the migrated database and its data distribution.
- Serverless cold starts and provider-region distance are hosted-environment concerns.
- The bounded retrieval strategy is not an approximate-nearest-neighbor index.
- Performance budgets require hosted telemetry and representative traffic before they can be stated
  as service objectives.
