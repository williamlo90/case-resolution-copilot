# Deployment And Rollback

Status: controlled-demo handoff. Deployment is manual and must not be described as automated CD.

## Release Identity

Record one full Git commit SHA before deployment. The frontend and backend must both return that
value in `X-Source-Revision`; `scripts/production-smoke.ps1` rejects a healthy but stale deployment.
Also record the two Vercel deployment IDs and the active Alembic revision without storing secrets.

## Promotion Order

1. Confirm a clean worktree and pass the serial release verifier.
2. Confirm the migration is backward compatible with the currently deployed application.
3. Create or retain the reviewed Neon rollback branch/checkpoint.
4. Apply migrations to the intended database and run `alembic current` plus `alembic check`.
5. Deploy the backend and verify readiness, revision identity, and closed production OpenAPI.
6. Deploy the frontend and verify its revision identity and authentication redirect.
7. Run the bounded authenticated role and workflow checks named in `POST_ENV_VERIFICATION.md`.

Do not promote the frontend first when it depends on a new backend contract. Do not apply a
destructive migration in the same change that removes application compatibility with the old
schema.

## Abort Criteria

Stop promotion when any of these occur:

- frontend and backend revisions differ from the intended commit;
- migration head or drift differs from the reviewed graph;
- readiness cannot reach the intended database;
- authentication redirects loop or a role gains authority it should not have;
- an unknown action outcome exposes retry;
- logs or responses expose secrets or internal exception text.

## Application Rollback

The release owner selects the last known-good Vercel deployment for each service, verifies its Git
SHA, and promotes backend before frontend unless the incident requires both to be removed from
traffic together. Run the smoke script against the rollback SHA and repeat the affected role check.
Record the incident, selected deployment IDs, operator, timestamps, and unresolved data risk.

Do not automatically downgrade PostgreSQL during an application rollback. Keep an additive schema
when the previous application can read it. If the previous application is incompatible, stop
traffic and choose a reviewed forward fix or a verified restore. A database restore requires the
separate `BACKUP_AND_RESTORE.md` procedure and explicit data-loss review.

## Ownership

- Release owner: approves promotion and application rollback.
- Database owner: approves migration, checkpoint, downgrade, or restore.
- Product authority: decides whether an incomplete controlled action requires business escalation.
- Evidence recorder: captures redacted commands, revisions, deployment IDs, results, and residual
  risk.

One person may fill several roles in a portfolio demo, but each decision must still be named.

## Verification

```powershell
$revision = git rev-parse HEAD
powershell -File scripts/production-smoke.ps1 -ExpectedRevision $revision
```

Passing smoke proves only revision identity and the bounded unauthenticated controls in the script.
It does not prove database rollback, role workflows, provider failure handling, or client readiness.
