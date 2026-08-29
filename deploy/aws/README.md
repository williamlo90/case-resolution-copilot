# AWS-Ready Deployment Pack

Status: reference architecture and placeholder templates. This repository has not been deployed to
AWS, and these files are not evidence of a running AWS environment.

The target keeps the application as a modular monolith while separating runtime processes:

- an ECS/Fargate API service runs FastAPI;
- an ECS/Fargate worker service runs Celery ingestion jobs;
- a single-instance ECS/Fargate scheduler service runs Celery Beat;
- a one-off ECS task applies Alembic migrations before service promotion;
- RDS PostgreSQL provides the transactional store and the `pgvector` extension;
- ElastiCache for Redis provides the Celery broker and short-lived job coordination;
- S3 is reserved for source attachments and evaluation artifacts after an application storage
  adapter is enabled;
- Secrets Manager supplies credentials at task start;
- CloudWatch receives container logs, metrics, alarms, and deployment events.

## Files

| File | Purpose |
| --- | --- |
| `ecs-api-task-definition.json` | FastAPI task definition template |
| `ecs-worker-task-definition.json` | Celery worker task definition template |
| `ecs-scheduler-task-definition.json` | Single-instance Celery Beat task definition template |
| `ecs-migration-task-definition.json` | One-off Alembic migration task template |
| `iam-task-policy.json` | Application task permissions template |
| `iam-deploy-policy.json` | Bounded CI deployment permissions template |
| `cloudwatch-alarms.json` | Suggested alarm inventory and initial thresholds |

Every value prefixed with `REPLACE_` must be resolved by the deployment system. Never replace a
secret placeholder with plaintext in Git. Task definition `secrets` entries reference Secrets
Manager ARNs; non-secret deployment settings remain ordinary environment variables.

## Image Contract

Build one immutable backend image and promote it by digest. Use the same image for API, worker,
scheduler, and migration tasks, changing only `command`. Remaining live validation work is listed
in [AWS deployment architecture](../../docs/architecture/AWS_READY_DEPLOYMENT.md).

The API, worker, scheduler, and migration definitions use the repository's actual runtime entry points.
Account-, image-, network-, and secret-specific values remain explicit `REPLACE_` placeholders.

## Validation Boundary

These JSON files are syntactically valid templates, not deployable definitions until placeholders
are substituted. Static validation does not prove AWS account quotas, IAM behavior, subnet routing,
database connectivity, container startup, migrations, or rollback.
