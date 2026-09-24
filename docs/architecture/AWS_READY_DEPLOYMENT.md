# AWS-Ready Deployment Architecture

Status: AWS-ready deployment architecture with executable CDK, static coverage, and one bounded
live validation completed on September 24, 2026. The disposable environment was destroyed after
validation. The always-on public demo remains on Vercel with Neon PostgreSQL.

## Deployment Shape

```text
Internet
   |
CloudFront HTTPS endpoint
   |
Application Load Balancer
   |
ECS/Fargate API service -------------- CloudWatch logs, metrics, alarms
   |                |
   |                +---- SQS + dead-letter queue ---- ECS/Fargate Celery worker
   |                            ^
   |                            +---- ECS/Fargate Celery Beat scheduler (one task)
   |                                             |
   +---- RDS PostgreSQL + pgvector --------------+
   |                                             |
   +---- Secrets Manager        versioned private S3 ---- Lambda validation trigger

EventBridge Scheduler -- at 45 min --> Step Functions teardown watchdog
                                          |-- delete Runtime stack
                                          +-- delete Foundation stack

GitHub Actions -- OIDC --> ECR + ECS deployment roles
                          |
                          +---- one-off migration task
```

The API, worker, scheduler, and migration task share one immutable backend image but run separate commands and scale
independently. This is process separation, not a microservice rewrite. The current frontend may
remain on Vercel and use Neon for the always-on demo; this AWS profile exists only for bounded live
infrastructure validation.

## Network Boundary

- Use at least two Availability Zones.
- In the low-cost ephemeral profile, put the ALB and ECS tasks in public subnets, assign public IPs
  to tasks for controlled outbound access, and allow no direct inbound traffic to those tasks.
- Keep RDS in isolated subnets. This avoids a continuously billed NAT Gateway during the short
  validation window.
- Allow inbound traffic to the API task only from the ALB security group on port `8000`.
- Allow PostgreSQL only from API, worker, and migration security groups.
- Grant SQS send permission to API/scheduler and consume plus retry permission to the worker.
- Never expose RDS. Public task IPs in this profile provide egress only; security groups admit API
  traffic solely from the ALB and no inbound traffic to worker, scheduler, or migration tasks.

This is not the recommended customer-pilot network. A serious pilot should move tasks into private
subnets and choose NAT gateways or VPC endpoints from measured availability and cost requirements.

## Runtime Components

### ECS/Fargate API

Run Uvicorn without `--reload`, behind an ALB with `/api/health/ready` as the target health check.
Start with `0.5 vCPU / 1 GiB`, two tasks for a pilot that needs Availability Zone redundancy, and
adjust only from observed CPU, memory, request latency, and database pressure.

### ECS/Fargate worker

Run Celery as a separate service. Start with low concurrency because model calls, database
connections, and provider quotas are the actual constraints. Use late acknowledgment only if the
ingestion task is idempotent, cap retries, add jittered backoff, and expose queue age plus terminal
failure metrics. Graceful shutdown must stop fetching new work before the Fargate stop timeout.

Each delivery claims at most one PostgreSQL-owned job. Its lease is the Celery hard time limit plus
a safety margin, so another worker cannot reclaim work while the first task may still be alive. A
killed task is recovered after lease expiry, while ownership fencing rejects stale results.

### ECS/Fargate scheduler

Run Celery Beat as a separate ECS service with desired count `1`. Set deployment minimum healthy
percent to `0` and maximum percent to `100`, so ECS stops the old scheduler before starting its
replacement instead of overlapping two Beat processes. PostgreSQL duplicate protection still makes
accidental duplicate deliveries harmless. The scheduler uses the same capability flags and secret
references as the worker because both construct the same validated application settings. Its
read-only root filesystem places the Beat schedule database and PID file in writable `/dev/shm`.

### RDS PostgreSQL and pgvector

The disposable profile uses encrypted, TLS-capable, single-AZ PostgreSQL with pgvector and deletion
settings selected for complete teardown. A customer pilot should add deletion protection, tested
backups/PITR, Performance Insights, and Multi-AZ according to its recovery objectives. Keep
transactional data and governed retrieval metadata together until measured scale justifies a
separate store.

Use RDS Proxy only after measuring connection churn. It adds cost and does not remove the need for
bounded SQLAlchemy pools in API and worker processes.

### SQS

SQS is the AWS Celery broker, not the system of record. Use long polling, server-side encryption,
a visibility timeout longer than the PostgreSQL job lease, and a bounded dead-letter policy.
Persistent job lifecycle, idempotency keys, and final outcomes remain in PostgreSQL. Redis remains
supported for local development, but the AWS profile avoids an always-on ElastiCache charge.

### S3

Use a private bucket with Block Public Access, versioning, SSE-KMS, lifecycle rules, and access logs
or CloudTrail data events where required. The executable portfolio profile uses
`validation-input/` and `validation-output/`: an S3-triggered Lambda reads a bounded evidence file,
computes its SHA-256 digest, and writes a content-addressed manifest. This validates the event path;
a full customer-source S3 adapter remains outside the current scope.

### Secrets Manager

Store database URLs, provider credentials, Clerk keys, signing secrets, and
credential-vault material as separate secrets where rotation ownership differs. ECS execution roles
may retrieve only the ARNs referenced by their task definition. Application task roles should not
receive general Secrets Manager read access.

## IAM Boundary

- GitHub Actions should assume an AWS role with OIDC; do not store long-lived AWS keys in GitHub.
- Separate ECS execution roles from application task roles.
- Runtime task roles do not receive general S3 access. Add bucket permissions only when an
  application storage adapter actually requires them.
- API and scheduler roles may send to the named SQS queue; the worker may receive, delete, and retry.
- The evidence Lambda may read only `validation-input/*`, write only `validation-output/*`, and
  send only to the named validation queue.
- The migration role receives database connectivity but no S3 or deployment authority.
- The CI role may push one ECR repository, register task definitions, update named ECS services,
  run the named migration task, and pass only approved roles.
- Scope permissions with account, region, cluster, service, repository, bucket prefix, and KMS key
  conditions during implementation. The templates retain a few AWS-required wildcard reads and
  must be reviewed with IAM Access Analyzer before activation.

## Release Sequence

1. Run repository quality gates and dependency audits.
2. Build the backend image once, scan it, push to ECR, and record its digest plus Git SHA.
3. Render task definitions from reviewed placeholders without logging secret values.
4. Confirm an RDS recovery point and backward-compatible migration plan.
5. Run the one-off migration task and require exit code `0`.
6. Deploy the single-instance scheduler, worker, then API with ECS deployment circuit breaker and
   rollback enabled.
7. Verify ALB health, source revision, authentication, queue processing, duplicate protection,
   database revision, and CloudWatch alarm delivery.
8. Promote traffic only after the bounded checks pass.

Never run migrations in every API or worker startup. Multiple tasks may race, and a failed migration
must stop promotion before new application code receives traffic.

## Rollback

Roll back application services to the previous image digest and task definition. Do not automatically
downgrade PostgreSQL. Prefer backward-compatible expand/contract migrations so the previous image
can run against the new schema. If a migration is incompatible, stop promotion and use the reviewed
forward fix or point-in-time restore procedure; record the data-loss boundary before proceeding.

For queued ingestion work, stop intake, allow safe tasks to finish, and preserve job rows. Do not
blindly replay tasks with unknown outcomes. Reprocessing must use the application idempotency key and
record a new attempt against the same logical job.

## Monitoring And Logs

Send structured stdout/stderr to separate API, worker, scheduler, and migration log groups with retention and
KMS settings chosen explicitly. Include correlation ID, job ID, tenant-safe identifiers, task name,
attempt number, duration, status, retrieval source counts, and model/provider latency. Exclude
credentials, OAuth tokens, customer message bodies, and raw evidence.

Initial alarms are inventoried in `deploy/aws/cloudwatch-alarms.json`. Before pilot traffic, add an
SNS destination and verify alarm delivery for:

- ALB 5xx, unhealthy targets, and p95 latency;
- ECS running-task count, CPU, memory, and deployment failures;
- Celery queue age, retries, terminal failures, and worker heartbeat;
- SQS queue depth, oldest-message age, receive count, and dead-letter growth;
- RDS storage, connections, CPU, replica lag if used, and backup failures;
- application readiness, provider failures, and unknown action outcomes.

## Cost-Aware Starting Point

The primary fixed costs are continuously running Fargate tasks, RDS,
ALB, CloudWatch ingestion/retention, and VPC endpoints. OpenAI and data transfer are variable costs.
Do not put exact monthly prices in repository claims because region and AWS pricing change.

For a temporary portfolio demonstration, keep desired task counts low, use short log retention,
schedule non-production shutdown, and consider single-AZ data services only when the reduced
resilience is explicit. For a controlled business pilot, prefer Multi-AZ data services, two API
tasks, tested backups, and alarm delivery. Use AWS Pricing Calculator before activation and set AWS
Budgets alerts before creating resources.

The executable `infra/aws` portfolio profile avoids a NAT Gateway by placing ECS tasks in public
subnets with public IPs and no direct inbound task rules. RDS remains isolated. This
profile also places CloudFront in front of an ALB whose HTTP ingress is restricted to the AWS-managed
CloudFront origin-facing prefix list. This is a deliberate short-lived cost trade-off, not the target
controlled-pilot network topology. Its VPC spans two Availability Zones, but its cost-limited RDS
resource is deliberately not Multi-AZ. EventBridge Scheduler starts a Step Functions teardown
watchdog at the hard 45-minute deadline, deleting Runtime before Foundation. A 35-minute operator
teardown target remains the manual control and requires teardown verification; the watchdog covers
workstation or terminal failure rather than replacing operator ownership.

## Readiness Gaps

This architecture becomes deployable only after:

- the API, worker, scheduler, and migration containers pass live startup/health validation;
- the single-instance scheduler ECS service is configured and its replacement behavior is observed;
- custom queue-age, retry, terminal-failure, and worker-heartbeat metrics are published;
- a full S3 source adapter is implemented if customer artifacts move beyond validation evidence;
- the executable CDK stacks pass live CloudFormation provisioning, connected
  S3-Lambda-SQS-Celery-PostgreSQL validation, and teardown verification;
- account-specific IAM, networking, DNS, certificates, backup, retention, and budgets are approved;
- migration, restore, SQS redrive, worker shutdown, and rollback drills are observed;
- GitHub OIDC deployment is configured and protected by an environment approval gate.
