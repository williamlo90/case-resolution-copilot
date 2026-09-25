# AWS CDK Validation Environment

Status: executable infrastructure-as-code with local synth coverage and a bounded live AWS
validation completed on September 24, 2026. The validation environment was fully destroyed
afterward.

This CDK app turns the reference architecture in `deploy/aws` into two explicit, disposable stacks:

- `CaseResolutionFoundation`: VPC, isolated RDS PostgreSQL with pgvector, SQS with a dead-letter
  queue, ECR, an ECS cluster, a private versioned S3 evidence bucket, Lambda validation, Secrets
  Manager, short-retention logs, and the AWS-side teardown watchdog.
- `CaseResolutionRuntime`: four task definitions, three ECS services, a public ALB, and a CloudFront
  HTTPS endpoint. Services begin at desired count `0`; the deployment script runs migrations before
  scaling scheduler, worker, and API to `1`.

The defaults are intentionally disposable and non-resilient. They are useful for a bounded portfolio
validation session, not a production or customer pilot. The always-on demonstration remains on
Vercel with Neon PostgreSQL. RDS, ALB, public IPv4, and
Fargate accrue charges while present. Scaling ECS to zero does not stop all charges.

At deployment start, EventBridge Scheduler is configured to start a Step Functions teardown
watchdog at the hard 60-minute deadline. The state machine requests deletion of Runtime first and
Foundation second. The operator targets manual teardown at 50 minutes and must run the destroy
script as soon as evidence is captured. The watchdog is a failure backstop, not a reason to leave
resources unattended.

Before deployment, the AWS account must already contain the manually managed
`portfolio-aws-monthly-budget` cost budget at USD 25 or lower. The Foundation script verifies this
precondition. The budget sends alerts; it is not a hard spending cap.
Both Foundation and Runtime scripts verify the budget type, currency, monthly limit, and expected
actual/forecast notification thresholds before creating additional cost.

## Local Validation

```powershell
cd infra/aws
npm ci
npm run build
npm test
npm run synth -- --profile case-resolution-portfolio
```

Synthesizing is read-only. Deploy commands below create billable AWS resources.

## Controlled Deployment

Run each command from the repository root:

These lifecycle scripts require PowerShell 7 and an active AWS SSO session.

```powershell
infra/aws/scripts/bootstrap.ps1
infra/aws/scripts/deploy-foundation.ps1 -AcknowledgeHourlyCost
infra/aws/scripts/set-application-secret.ps1 `
  -SecretFile infra/aws/application-secrets.local.json
infra/aws/scripts/publish-image.ps1 -SourceRevision <full-git-sha>
infra/aws/scripts/deploy-runtime.ps1 `
  -SourceRevision <full-git-sha> `
  -AcknowledgeHourlyCost
infra/aws/scripts/validate-live.ps1
```

Create `application-secrets.local.json` from `application-secrets.example.json`. The local file is
ignored by Git. The upload script validates required fields and never prints their values.

The Runtime deployment refuses placeholder secrets, deploys services at zero, runs the one-off
Alembic task, requires exit code `0`, then starts scheduler, worker, and API in that order.
If any service fails to stabilize, the script scales all three services back to zero.
Image publication requires a clean worktree at the requested commit, waits for ECR scanning, rejects
critical/high findings, and writes the verified digest to ignored `release.local.json`. Runtime
deployment consumes that digest instead of trusting a mutable tag.

`validate-live.ps1` checks both CloudFormation stacks, CloudFront and ALB health, three stable ECS
services, the connected S3-to-Lambda-to-SQS-to-Celery validation path, an empty SQS dead-letter
queue, and the live PostgreSQL migration and pgvector state. It writes sanitized local evidence
without credentials or account identifiers.

For the portfolio record, capture only these high-signal console views before teardown: completed
CloudFormation stacks; running ECS services; the SQS queue and empty DLQ; the S3 input/output objects;
the Lambda invocation log; RDS availability/migration evidence; CloudFront health; and the passing
validation summary. Also capture the scheduled watchdog and Step Functions definition. The
operator targets teardown at 50 minutes; the watchdog starts teardown at the hard 60-minute deadline.

## Teardown

```powershell
infra/aws/scripts/destroy.ps1 `
  -SourceRevision <full-git-sha> `
  -AcknowledgeDestroy
```

Destroy both stacks after the validation window. Verify in Cost Explorer and the resource consoles
that no tagged RDS, ALB, CloudFront, ECS, Lambda, SQS, EIP, Secrets Manager, or orphaned network
resources remain.

## Deliberate Trade-offs

- No NAT Gateway: ECS tasks use public subnets and public IPs for outbound provider access, while
  task security groups expose no inbound port except API traffic from the ALB.
- The public ALB accepts HTTP only from AWS's CloudFront origin-facing prefix list; users reach the
  API through CloudFront HTTPS.
- RDS stays in isolated subnets and accepts PostgreSQL traffic only from API or background task
  security groups.
- SQS replaces the fixed ElastiCache broker cost for the AWS profile. PostgreSQL remains
  authoritative for job lifecycle and idempotency; the dead-letter queue must remain empty.
- Single-AZ RDS minimizes a short validation session's cost and is not resilient.
- The VPC spans two Availability Zones for subnet layout, while cost-limited RDS deliberately runs
  without Multi-AZ resilience.
- Container Insights, autoscaling, RDS storage autoscaling, retained snapshots, and long log
  retention are disabled in this profile.
- The Vercel frontend and Neon database remain the always-on portfolio demo. This AWS profile is a
  separate, short-lived infrastructure validation and is not its production hosting environment.

The honest claim is **live-validated, disposable AWS deployment architecture with executable CDK**.
It is not an always-on AWS production deployment; the public application remains on Vercel and Neon.
See the sanitized [validation record](../../docs/evidence/aws-live-validation/README.md).
