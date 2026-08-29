# AWS Deployment Operations

Status: pre-deployment runbook. No AWS environment has been exercised by this repository.

## Required Inputs

Record these as deployment metadata, not secrets:

- AWS account, region, environment, and release owner;
- Git commit SHA and immutable ECR image digest;
- ECS cluster, API service, worker service, single-instance scheduler service, and migration task family;
- RDS cluster/instance identifier and current Alembic revision;
- Redis replication group identifier;
- S3 bucket name and approved prefixes;
- rollback task definition revisions and recovery-point timestamp.

Keep credentials and connection strings in Secrets Manager. The deployment log may contain secret
ARNs but must never contain secret values.

## Preflight

1. Confirm quality gates pass on the exact commit.
2. Confirm the image scan has no unaccepted critical/high findings.
3. Confirm all `REPLACE_` placeholders were resolved by controlled rendering.
4. Confirm API, worker, and scheduler use the same image digest and production commands.
5. Confirm `SUPPORT_COPILOT_DEV_MIGRATE=false` and `SUPPORT_COPILOT_DEV_SEED=false`.
6. Confirm RDS backup/PITR health, available storage, TLS, and expected Alembic revision.
7. Confirm Redis TLS/auth, `noeviction`, capacity, and connection limits.
8. Confirm task security groups have no public database or Redis path.
9. Confirm CloudWatch log groups, retention, alarms, SNS route, and budgets exist.
10. Confirm the previous task definitions and image digest remain available.

## Deploy

1. Push the immutable image and record its digest.
2. Register migration, scheduler, worker, and API task definitions using that digest.
3. Run the migration task in private subnets and wait for a stopped task with exit code `0`.
4. Query `alembic current` from a bounded verification task and compare it with the repository head.
5. Update the scheduler service with desired count `1`, minimum healthy percent `0`, and maximum
   percent `100`; verify only one Beat task is running. Update the worker service and verify desired
   count, heartbeat, broker connectivity, and no terminal ingestion failures.
6. Update the API service with circuit breaker rollback enabled. Wait for service stability.
7. Verify ALB readiness, source revision, authentication, tenant isolation, and one read-only case.
8. Submit one synthetic ingestion request. Confirm job status, source retrieval, duplicate rejection,
   bounded retry behavior, and a successful reprocess path.
9. Confirm logs are structured and contain no secret or raw evidence payload.
10. Confirm all critical alarm routes receive a test notification, then close the release record.

## Abort Conditions

Abort or roll back when:

- migration exits non-zero or database revision is unexpected;
- readiness cannot reach RDS or authentication dependencies;
- ECS cannot stabilize within the reviewed deployment window;
- worker retries are unbounded, duplicates create multiple logical jobs, or job outcomes disappear;
- Redis evicts broker data or loses authenticated TLS connectivity;
- tenant isolation, approval, action safety, or secret redaction regresses;
- monitoring is absent, alarm delivery fails, or the deployed digest differs from the release record.

## Application Rollback

1. Stop new ingestion when worker behavior or data compatibility is uncertain.
2. Revert API, worker, and scheduler services to the previous task definition revisions while
   preserving a single running scheduler.
3. Wait for stable target health and worker heartbeats.
4. Do not downgrade the database automatically. Confirm the previous image supports the current
   schema.
5. Reconcile running, retrying, and outcome-unknown jobs before reopening intake.
6. Repeat authentication, tenant isolation, job idempotency, and read-only case checks.
7. Record impact, timestamps, image digests, schema revision, and remaining uncertainty.

## Database Recovery

Use point-in-time restore only after the incident owner defines the acceptable recovery point and
potential data loss. Restore to a new RDS instance, validate migrations and tenant-scoped records,
then change the database secret through a controlled cutover. Do not overwrite the affected database
or silently repoint production.

## Redis Recovery

Redis is not authoritative for final job state. After failover or replacement, restart workers only
after PostgreSQL job records are inspected. Requeue eligible jobs through the application reprocess
operation; never replay raw broker messages or jobs with unknown side effects.

## S3 Recovery

Use object versioning and the audit trail to restore a source artifact. Preserve the original object
version and its checksum. Reprocessing must bind the job to the intended version so changed source
material cannot silently alter an already reviewed outcome.

## Routine Operations

- Review AWS Cost Explorer and Budgets weekly during a pilot.
- Review IAM Access Analyzer and unused permissions monthly.
- Rotate provider and signing credentials under a tested overlap plan.
- Patch base images and dependencies through the normal quality gate.
- Test RDS restore, migration rollback boundary, Redis interruption, and ECS rollback quarterly or
  before a higher-risk pilot.
- Tune task sizes, concurrency, retention, and alarms from observed data; record each change.
