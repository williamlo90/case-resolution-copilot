# AWS-Ready Deployment Architecture

Status: proposed deployment architecture. No AWS deployment is claimed.

## Deployment Shape

```text
Internet
   |
Route 53 + ACM
   |
Application Load Balancer
   |
ECS/Fargate API service -------------- CloudWatch logs, metrics, alarms
   |                |
   |                +---- ElastiCache Redis ---- ECS/Fargate Celery worker
   |                            ^
   |                            +---- ECS/Fargate Celery Beat scheduler (one task)
   |                                             |
   +---- RDS PostgreSQL + pgvector --------------+
   |                                             |
   +---- Secrets Manager                         +---- private S3 bucket

GitHub Actions -- OIDC --> ECR + ECS deployment roles
                          |
                          +---- one-off migration task
```

The API and worker share one immutable backend image but run separate commands and scale
independently. This is process separation, not a microservice rewrite. The current frontend may
remain on Vercel or later move to a separate hosting decision; it is outside this backend-focused
AWS pack.

## Network Boundary

- Use at least two Availability Zones.
- Put the ALB in public subnets. Put ECS tasks, RDS, and ElastiCache in private subnets.
- ECS tasks need controlled egress through NAT or VPC endpoints for ECR, CloudWatch, S3, Secrets
  Manager, and any explicitly enabled external provider.
- Allow inbound traffic to the API task only from the ALB security group on port `8000`.
- Allow PostgreSQL only from API, worker, and migration security groups.
- Allow Redis only from API, worker, and scheduler security groups. Require TLS and authentication.
- Do not expose RDS, Redis, or task public IPs.

For a cost-limited portfolio environment, one NAT gateway is cheaper but loses Availability Zone
independence. A serious pilot should use one NAT gateway per Availability Zone or reduce NAT use
with VPC endpoints after measuring the actual cost tradeoff.

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
read-only root filesystem exposes only an ephemeral writable `/tmp` volume for the Beat schedule
database and PID file.

### RDS PostgreSQL and pgvector

Use PostgreSQL with encryption at rest, TLS in transit, automated backups, deletion protection,
Performance Insights, and a parameter group sized for the chosen instance. Enable `vector` through
a reviewed migration or bootstrap step. Keep transactional application data and governed retrieval
metadata together until measured scale justifies a separate store.

Use RDS Proxy only after measuring connection churn. It adds cost and does not remove the need for
bounded SQLAlchemy pools in API and worker processes.

### ElastiCache Redis

Redis is the Celery broker and coordination layer, not the system of record. Enable encryption in
transit, encryption at rest, authentication, automatic failover where the pilot requires it, and a
`noeviction` policy for broker safety. Persistent job lifecycle, idempotency keys, and final outcomes
must remain in PostgreSQL.

### S3

Use a private bucket with Block Public Access, versioning, SSE-KMS, lifecycle rules, and access logs
or CloudTrail data events where required. Suggested prefixes are `ingestion/` for source objects and
`evaluations/` for generated evidence. The current application does not yet prove an S3 storage
adapter; bucket access is architecture-ready until that adapter and its tests exist.

### Secrets Manager

Store database URLs, provider credentials, Clerk keys, Redis authentication, signing secrets, and
credential-vault material as separate secrets where rotation ownership differs. ECS execution roles
may retrieve only the ARNs referenced by their task definition. Application task roles should not
receive general Secrets Manager read access.

## IAM Boundary

- GitHub Actions should assume an AWS role with OIDC; do not store long-lived AWS keys in GitHub.
- Separate ECS execution roles from application task roles.
- API and worker task roles receive only required S3/KMS actions and no infrastructure mutation.
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
- Redis evictions, memory, connections, and failover;
- RDS storage, connections, CPU, replica lag if used, and backup failures;
- application readiness, provider failures, and unknown action outcomes.

## Cost-Aware Starting Point

The primary fixed costs are continuously running Fargate tasks, RDS, ElastiCache, NAT gateways,
ALB, CloudWatch ingestion/retention, and VPC endpoints. OpenAI and data transfer are variable costs.
Do not put exact monthly prices in repository claims because region and AWS pricing change.

For a temporary portfolio demonstration, keep desired task counts low, use short log retention,
schedule non-production shutdown, and consider single-AZ data services only when the reduced
resilience is explicit. For a controlled business pilot, prefer Multi-AZ data services, two API
tasks, tested backups, and alarm delivery. Use AWS Pricing Calculator before activation and set AWS
Budgets alerts before creating resources.

## Readiness Gaps

This architecture becomes deployable only after:

- the API, worker, scheduler, and migration containers pass live startup/health validation;
- the single-instance scheduler ECS service is configured and its replacement behavior is observed;
- custom queue-age, retry, terminal-failure, and worker-heartbeat metrics are published;
- an S3 adapter is implemented if source artifacts are placed in S3;
- infrastructure is represented in Terraform, CDK, CloudFormation, or an equivalent reviewed tool;
- account-specific IAM, networking, DNS, certificates, backup, retention, and budgets are approved;
- migration, restore, Redis interruption, worker shutdown, and rollback drills are observed;
- GitHub OIDC deployment is configured and protected by an environment approval gate.
