# Post-ENV Verification

Status: Procedure defined. The existing Neon, Clerk, and Vercel projects must be rebound and
reverified against the final reconstruction commit.

## Before Adding Values

- Confirm Clerk remains the selected identity provider and Organizations remains disabled.
- Confirm `.env` and provider credential files are ignored.
- Use test credentials and a disposable database.
- Set spending limits and disable automatic overage where supported.
- Approve each external command and any resource-intensive verification separately.

## C1 - Secret Hygiene

1. Add values locally or in the deployment secret manager, not in chat.
2. Run `git status --short --ignored` and confirm no secret file is staged.
3. Search staged content for connection strings, tokens, private keys, and provider credentials.
4. Rotate any value that appears in logs or Git history.

Clerk values belong only in `frontend/.env.local`, `backend/.env`, or the deployment secret
manager. Use `docs/runbooks/AUTHENTICATION_ACTIVATION.md` for the exact names and account-linking
sequence.

## C2 - Database And Authentication

Run one lightweight process at a time:

```powershell
cd backend
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic check
.\scripts\run_integration_tests.ps1 -ConnectionOnly
.\scripts\run_integration_tests.ps1 -ConfirmDestructiveDisposableDatabase
```

To retain the bounded query-plan metrics in redacted output, run only the scale proof with:

```powershell
.\scripts\run_integration_tests.ps1 `
  -ConfirmDestructiveDisposableDatabase `
  -ShowCapturedOutput `
  -TestPath tests\integration\test_scale_query_plans.py
```

The integration gate requires an explicitly reviewed disposable direct Neon `TEST_DATABASE_URL`
stored unmodified in `backend/.env.test.local`, plus `TEST_DATABASE_SCOPE=disposable` and a
`TEST_DATABASE_ENDPOINT_ID` matching that URL. The runner selects the `psycopg` driver in memory,
requires an explicit destructive switch, and is mandatory for database-backed pytest output. Then
verify liveness, readiness, sign-in/out, invitation, tenant isolation, role denial, session expiry,
and provider outage behavior.

For Clerk, link the invited `user_...` subject with the dry-run-first
`scripts.link_clerk_identity` command. Verify the initial administrator manually before creating
additional role accounts. Do not paste session tokens into shell commands or evidence files.

Historical predecessor evidence captured on 24 July 2026: PostgreSQL 18.4 connectivity, pgvector, migration
downgrade/upgrade, and all `51` integration tests passed. The active Neon database reached
`20260728_0017 (head)` with a clean drift check on 28 July 2026. A readable pre-migration checkpoint
and a disposable point-in-time restore to revision `20260723_0015` were verified separately. The
30 July quality-hardening gate separately passed `43/43` current integration tests through source
head `20260730_0019`, including measured plans over 10,000 policy clauses and 50,000 cases. The
active `development` database was then promoted to `20260730_0019` after a seven-day rollback branch
was retained. Post-promotion checks found all 14 intended indexes, clean drift, unchanged 3/4/8
case/version/clause counts, and healthy hosted readiness. The production Clerk administrator
sign-in was manually verified on Vercel. The complete role matrix, session-expiry/provider-outage
drills, and application connection cutover remain open C2 gates.

## C3 - Provider Contracts

Activate and test one provider at a time using
`docs/runbooks/PROVIDER_ACTIVATION.md`. Capture success, safe failure, timeout, malformed response,
rate limit, revocation, redaction, and rollback evidence. Side-effect providers also require
idempotency, ambiguous-timeout, receipt lookup, and reconciliation evidence.

The OpenAI Decision Brief happy path and idempotent repeat refresh were manually verified in
production. External case-source and action-target providers have not been selected, and the full
OpenAI failure matrix has not been exercised with live credentials.

## C4 - Acceptance

- Complete manual role-based journeys for specialist, supervisor, administrator, and auditor.
- Confirm generic UI labels and no active legacy write consumer.
- Rehearse backup/restore and one incident scenario.
- Run `scripts/production-smoke.ps1` after every frontend/backend deployment.
- Record unresolved security, performance, accessibility, and provider risks.
- Do not claim pilot readiness until every required gate has attributable evidence.

Deployment header expectations and external security boundaries are documented in
`docs/runbooks/SECURITY_HARDENING.md`.

The predecessor release passed both Vercel deployment checks, the bounded production smoke,
authenticated main-route navigation, Decision Brief idempotent refresh, and published-policy
inspection. Treat that as historical context, not proof for the current commit. The remaining C4
work requires current hosted verification, client-owned case/action sandboxes, provider failure
evidence, monitored cutover/rollback, and incident drills.

## Resource Boundary

Local `next dev` browser automation, Turbopack, Docker, load/stress tests, watch processes, and
background workers remain outside the default path. A bounded hosted-browser acceptance journey is
allowed when explicitly requested and must stop after the defined checks.
