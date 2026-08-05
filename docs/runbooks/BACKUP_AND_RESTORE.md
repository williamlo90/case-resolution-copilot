# Backup And Restore

Status: Procedure defined. The predecessor deployment completed a disposable point-in-time restore;
the current rebuild still requires revision-bound cutover evidence.

## Ownership And Targets

Before activation, record the database provider, backup owner, restore owner, retention period,
encryption method, region, target RPO, and target RTO. Provider snapshots are not considered proven
until a restore into a disposable database succeeds.

## Backup Preconditions

- The target database and environment are unambiguous.
- Credentials are supplied through protected environment or provider tooling.
- The backup includes schema and data required by the current Alembic head.
- Backup output is encrypted and stored outside the repository.
- A checksum, creation time, application commit, Alembic revision, and database family/version are
  recorded without exposing the connection URL.

## Restore Rehearsal

1. Create a disposable isolated database.
2. Restore the selected provider snapshot or logical backup.
3. Point only the test process at the disposable database.
4. Confirm the recorded Alembic revision, then run reviewed forward migrations if required.
5. Verify organization, case, policy, review, action, receipt, settings, audit, and governance row
   counts.
6. Run tenant-isolation, immutable-snapshot, idempotency, and readiness checks.
7. Sample legacy-to-generic lineage and unresolved outcome records.
8. Destroy the disposable target using provider-approved controls after evidence is retained.

## Recovery Rules

- Prefer point-in-time recovery or a verified snapshot for database-wide corruption.
- Prefer a forward corrective migration for a narrow schema defect.
- Never replay provider writes to reconstruct missing action state.
- Preserve outcome-unknown records until the target system is reconciled.
- Keep legacy workflow routes unmounted; use reviewed offline backfills for historical records.

## Acceptance Evidence

A backup process is operational only when restore duration, resulting revision, integrity checks,
tenant checks, and the responsible operator are recorded. The historical rehearsal below supplies
disposable restore timing and core integrity evidence for the predecessor deployment. It does not
prove cutover or recovery time for the current rebuild.

## Historical Rehearsal: 28 July 2026

The active application database was identified as the Neon branch labelled `development`. Before
the release migrations, `pre-0016-active-backup-20260728` was created with seven-day retention.
Read-only verification confirmed:

- Alembic revision `20260723_0015`;
- three cases;
- one organization;
- four governed policy versions;
- absence of the two columns introduced by migration `20260728_0016`.

After migration, the active branch retained the same case, organization, and policy counts and
reported revision `20260728_0017` with both columns present.

Neon Free did not allow a child branch to be created from the auto-expiring checkpoint. A direct
point-in-time branch from the active branch was therefore used instead:

- branch: `restore-pitr-rehearsal-20260728`;
- restore point: 28 July 2026 at 21:13:17 Asia/Jakarta;
- isolation: separate branch with one-day auto-delete;
- branch creation: approximately 2.8 seconds;
- first validation query: approximately 2.8 seconds;
- restored revision: `20260723_0015`;
- restored core counts: three cases, one organization, and four governed policy versions;
- migration boundary: both columns introduced by `20260728_0016` were absent.

This proves that a selected point in the active branch history can be restored into an isolated
target and queried with the expected core state. The measured 2.8 seconds is branch provisioning,
not application recovery RTO. A maintenance-window rehearsal must still transfer or temporarily
replace the application connection, run tenant and workflow checks, and demonstrate rollback
without changing production during this evidence-only exercise.

## Historical Migration Checkpoint: 30 July 2026

Before revisions `20260730_0018-0019` were applied, `pre-0019-rollback-20260730` was forked from the
active `development` branch with its current data and schema. It was configured for seven-day
retention, expiring on 6 August 2026 at 20:38 Asia/Jakarta. The active branch retained three cases,
four governed policy versions, and eight governed policy clauses after promotion to `0019`.

This checkpoint is a rollback option for the migration window, not new restore evidence. The
earlier point-in-time restore rehearsal remains the proof that an isolated historical state can be
provisioned and queried; application cutover and recovery RTO remain open.
