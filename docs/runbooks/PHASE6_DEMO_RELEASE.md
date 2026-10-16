# Phase 6 synthetic demo release

Scope: controlled portfolio demo using synthetic data and deterministic providers. CI artifacts govern container, security, and recovery validation. Previous-release binary compatibility and application restore cutover remain separate gates.

## What runs

`compose.demo.yaml` starts four services on an isolated container host: PostgreSQL with pgvector, a one-shot migration and seed job, FastAPI, and a production-built Next.js frontend. The API waits for the seed job; the frontend waits for API readiness. PostgreSQL is internal to Compose. Only API port 8000 and frontend port 3000 bind to host loopback. Runtime memory caps are 1 GiB each for PostgreSQL, migration, and API, plus 1.5 GiB for the frontend; allow extra memory for serial image builds. No Redis, Celery, cloud provider, browser automation, or paid AI key is needed for this path.

The seed creates demo identities, cases, policies, connections, settings, quality records, and notifications. The action target and AI provider are deterministic. A random database password is saved in ignored `local/phase6/demo.env`, never printed. The named database volume survives normal `Down`; treat it as disposable demo data, not a backup.

The backend demo uses Alpine and locked Python dependencies; migrations and seeds call the installed virtual environment directly, without installing dependencies at runtime. The frontend image contains Next.js standalone output and the Node runtime. The PostgreSQL demo builds pgvector v0.8.7 from a verified source commit in a separate build stage.

On a **separate isolated container host** with Docker Compose and adequate memory:

```powershell
./scripts/demo-compose.ps1 -Action Config
./scripts/demo-compose.ps1 -Action Up -IsolatedHost
./scripts/demo-compose.ps1 -Action Smoke -IsolatedHost
./scripts/demo-compose.ps1 -Action Down
```

`Up` is the one-command build, migrate, seed, and start path. Open `http://127.0.0.1:3000/cases` on that host. Keep the ports on loopback and do not expose this deterministic identity mode to a network. `Down` stops containers and retains the volume; deleting the volume is a separate, deliberate action on the disposable host.

The evaluator CLI runs from the source checkout, separately from the demo image. From `backend/`, `uv run python -m scripts.evaluate_case_resolution_v2 validate-corpus --root evaluations/case_resolution_v2_phase4` performs static corpus validation with zero product executions. For an already sealed, unscored Phase 4 run, use `uv run python -m scripts.score_phase4_run --root evaluations/case_resolution_v2_phase4 --split holdout --output <sealed-run> --enforce-gate`. This scores recorded observations; it does not authorize another holdout capture. Runtime capture stays in the isolated Phase 4 lane.

The [isolated CI smoke](../../.github/workflows/phase6-demo-smoke.yml) runs on the dedicated candidate branch or manual dispatch. It builds images serially, scans both images for high/critical OS and library findings, starts the stack, checks API readiness and a seeded case count, loads the frontend case route, restarts the API, checks readiness again, and restores a logical backup into a second disposable database. It compares restored case counts and the Alembic revision, records image identities, then tears down the disposable volume. A separate CI job checks PostgreSQL migrations, authority, action idempotency, and fail-closed unknown-outcome recovery after application recreation. It has not passed merely because the workflow file exists. The standard quality gate separately runs source tests, dependency audits, and a production frontend build. Any image finding must be reviewed and fixed before a release claim.

## Release and recovery check

Record the commit SHA, backend/frontend image IDs, Compose config hash, Alembic head, seed count, start/restart timestamps, and CI run URL. A green readiness response alone is insufficient: verify a Specialist cannot approve their own consequential action, a Supervisor's approval is bound to the proposal snapshot, an Auditor cannot mutate, and tenant isolation holds. The existing contract/unit tests cover these controls; the isolated workflow verifies the container wiring. A disposable PostgreSQL integration run remains necessary for database-backed authority and action journeys.

For application rollback, retain the last known-good backend and frontend images by digest. Stop traffic; verify the old binaries accept the **current schema**; start the backend image, then the frontend image; repeat readiness and affected role checks. The CI drill deliberately replaces the backend with an image that exits, confirms the failure, restores the known-good candidate image/config, then checks image identity, readiness, and unchanged schema. This proves bounded replacement mechanics; compatibility with an older product release remains a separate gate. Do not downgrade schema as an automatic response. Migration `20261013_0025` creates append-only resolution evidence and its downgrade drops that table, so a schema rollback would destroy records. If binary compatibility fails, use a reviewed forward fix or an isolated, verified database restore with an explicit data-loss boundary. The current rebuild's restore cutover has not been demonstrated; follow [Backup And Restore](BACKUP_AND_RESTORE.md).

After any restart, inspect every `outcome_unknown` action before resuming execution. An unknown outcome must not expose a safe retry or count as a verified resolution. Reconcile by reading the synthetic target's independent receipt; preserve the unknown state if no verified read-back exists. The targeted [database journey](../../backend/tests/integration/test_case_action_api.py) checks unknown-outcome retry blocking and reconciliation, but a container restart by itself does not prove that full business recovery path. Keep the unverified scenario open until the isolated integration journey passes.

## Release gate

- Migration graph and source checks pass on the exact release commit.
- Compose configuration passes locally; build, startup, restart smoke, and database integration pass on an isolated host.
- Dependency, repository secret, and image scans have no unresolved blocking findings; record their actual reports.
- Synthetic seeds and deterministic mode are verified, with no real customer data or provider credential in the demo image.
- Binary rollback compatibility or a documented forward-fix/restore path is demonstrated on disposable data. Unknown-outcome recovery is verified after restart.
- Review the [V2 production readiness tracker](../production-documentation/PRODUCTION_READINESS_TODO.md) before claiming a production release; external activation and live reliability gates remain explicit.

Phase 6 receives one final Git checkpoint when its gate has evidence. Candidate validation keeps Phase 5's uncommitted human-study preparation separate. The operator's review and any isolated host access are the final handoff after the engineering package is ready.
