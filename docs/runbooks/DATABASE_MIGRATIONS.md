# Database Migration Runbook

## Safety Boundary

Application migrations are Alembic-owned and target PostgreSQL with pgvector. Never rehearse a
downgrade or destructive test against a development or production branch. Use a direct connection
to an explicitly disposable database and the guarded runner.

Do not print connection strings, passwords, endpoint URLs, or provider tokens in evidence.

## Static Verification

Static checks require no database:

```powershell
cd backend
uv run python -m scripts.check_migration_graph
uv run alembic heads
uv run alembic history
```

These checks prove graph shape and source consistency. They do not prove that PostgreSQL accepts the
migrations or that runtime indexes are present.

## Disposable Database Contract

Store the following only in ignored `backend/.env.test.local`:

```dotenv
TEST_DATABASE_URL=postgresql://...
TEST_DATABASE_SCOPE=disposable
TEST_DATABASE_ENDPOINT_ID=ep-...
```

The endpoint must be direct, TLS-enabled, and dedicated to destructive tests. Then run:

```powershell
./scripts/run_integration_tests.ps1 -ConnectionOnly
./scripts/run_integration_tests.ps1 -ConfirmDestructiveDisposableDatabase
```

The runner validates the endpoint identity, redacts captured output, sets the destructive guard for
the child process, downgrades to base, upgrades to head, isolates every test, and removes the
credential from the process environment afterward.

## Application Migration

For a reviewed target environment:

1. Confirm the database branch, owner, region, and recovery point.
2. Create or verify a rollback branch or backup.
3. Record the current application revision and Alembic revision.
4. Run `uv run alembic upgrade head` once.
5. Run `uv run alembic current` and `uv run alembic check`.
6. Ingest versioned policy source files with `uv run python scripts/ingest_policies.py` when the
   environment requires seed policies.
7. Verify readiness, tenant isolation, permissions, review immutability, action idempotency, and
   expected indexes.
8. Record redacted evidence and the rollback decision owner.

Do not run development seed scripts in production.

## Failure Handling

- Stop on the first migration error; do not repeatedly rerun an unknown partial state.
- Preserve the migration output with credentials redacted.
- Prefer a reviewed forward correction for a narrow schema defect.
- Use point-in-time recovery or a verified backup for broad corruption.
- Do not downgrade populated tables unless the migration explicitly proves the operation safe.
- Keep readiness unhealthy until schema, data integrity, and tenant checks pass.

## Current Evidence Boundary

The reconstructed repository passes migration graph and source checks. Its disposable PostgreSQL
suite is present but has not been rerun for the exact reconstruction commit. Historical Neon
results from the predecessor repository are operational context, not current-revision evidence.
