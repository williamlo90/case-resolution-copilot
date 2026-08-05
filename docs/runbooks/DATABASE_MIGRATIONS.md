# Database Migration And Rollback

## Preconditions

- `SUPPORT_COPILOT_DATABASE_URL` identifies the reviewed target PostgreSQL database.
- The application commit and Alembic revision are reviewed together.
- Non-disposable environments have a verified backup and rollback owner.
- The database URL is never printed in logs or evidence.

## Inspect And Upgrade

From `backend/`:

```powershell
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe scripts/setup_checkpoints.py
.venv\Scripts\python.exe scripts/ingest_policies.py
```

Then verify `GET /api/health/ready` returns `200` with database status `healthy`.
Legacy workflow routes are not mounted. Do not add a runtime toggle that re-enables them; use the
reviewed backfill commands for historical records.

## Current Schema Scope

The migration chain includes organizations, generic cases and business snapshots, governed policy
versions and evidence, decision briefs, reviews, controlled actions, settings, notifications,
quality evidence, governance state, and the older compatibility records.

Some inherited table and column names remain travel-shaped for migration compatibility. They are an
internal implementation detail and not the support product contract.

LangGraph owns `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, and
`checkpoint_migrations`. Alembic deliberately excludes those four tables from application-schema
autogeneration; `scripts/setup_checkpoints.py` remains their lifecycle command.

As of 30 July 2026, the deployed application connection targets the Neon branch labelled
`development`, not the empty branch labelled `production`. The reviewed environment connection is
the authority. Do not rename branches or replace the connection during a release without a
separate cutover and rollback plan.

Source revision `20260730_0018` adds case queue keyset indexes. Revision `20260730_0019` adds
decision-generation reservation storage, HNSW policy-clause retrieval, JSONB applicability indexes,
and trigram case search. Both passed the guarded auto-expiring disposable-branch gate and were then
promoted to the active `development` branch under the checkpoint procedure below.

## Rollback

Review the exact migration `downgrade()` and data-loss impact first:

```powershell
.venv\Scripts\python.exe -m alembic downgrade -1
.venv\Scripts\python.exe -m alembic current
```

Prefer a forward corrective migration when rollback could discard business records. A syntactically
available downgrade is not proof of lossless recovery.

## Current Evidence

Revisions `20260728_0016` and `20260728_0017` were applied first to a disposable Neon child branch
and then to the active application database after a seven-day pre-migration branch was retained.
The active database reported `20260728_0017 (head)` and a clean `alembic check`.

Revisions `20260730_0018` and `20260730_0019` subsequently passed a full downgrade-to-base and
upgrade-to-head cycle plus `43/43` PostgreSQL integration tests on a separate disposable child
branch. Query-plan evidence covered 10,000 policy clauses and 50,000 cases. That branch was deleted
after capture.

Before active promotion, `pre-0019-rollback-20260730` was forked from `development` with data and
schema and configured to expire on 6 August 2026 at 20:38 Asia/Jakarta. The direct, TLS-required
active endpoint was at `20260728_0017`, had no other active sessions, and contained three cases,
four governed policy versions, and eight governed policy clauses. The additive `0018-0019`
migrations then completed transactionally. Post-promotion verification found:

- `20260730_0019 (head)` and no Alembic upgrade operations;
- all 14 intended queue, generation, retrieval, and search indexes;
- `pg_trgm` and `vector` extensions;
- the decision-generation lease table;
- unchanged counts of three cases, four governed policy versions, and eight clauses;
- hosted liveness and readiness `200`, with the database reported healthy.

The first post-promotion drift check correctly exposed that 13 migration-managed indexes were not
represented in ORM metadata. Commit `b8f65d0` aligned the metadata and added regression tests; the
clean drift result above was captured after that fix. This proves active forward migration and
schema consistency. It still does not prove an application connection cutover or measured recovery
time.

The read-only legacy inventory on 30 July 2026 found `15` rows in legacy policy storage and `10`
cross-boundary foreign keys. Legacy table removal is therefore not approved. Re-run:

```powershell
.venv\Scripts\python.exe -m scripts.inventory_legacy_storage
```

The command exports counts and schema relationships only; it never exports row contents.
